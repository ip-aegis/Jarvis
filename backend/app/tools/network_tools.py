"""
LLM tools for network device monitoring and management.
"""
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import NetworkDevice, NetworkMetric, NetworkPort
from app.tools.base import Tool, tool_registry

# =============================================================================
# Query Tools (READ)
# =============================================================================


async def list_network_devices_handler() -> dict:
    """Get a list of all monitored network devices with their status."""
    db = SessionLocal()
    try:
        devices = db.query(NetworkDevice).all()
        return {
            "network_devices": [
                {
                    "id": d.id,
                    "name": d.name,
                    "ip_address": d.ip_address,
                    "device_type": d.device_type,
                    "vendor": d.vendor,
                    "model": d.model,
                    "status": d.status,
                    "port_count": d.port_count,
                    "location": d.location,
                    "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                    "uptime_days": round(d.uptime_seconds / 86400, 1) if d.uptime_seconds else None,
                }
                for d in devices
            ],
            "total": len(devices),
        }
    finally:
        db.close()


async def get_network_device_metrics_handler(
    device_id: int = None,
    name: str = None,
) -> dict:
    """Get current metrics for a specific network device by ID or name."""
    db = SessionLocal()
    try:
        # Find device
        if device_id:
            device = db.query(NetworkDevice).filter_by(id=device_id).first()
        elif name:
            device = db.query(NetworkDevice).filter_by(name=name).first()
        else:
            return {"error": "Must provide either device_id or name"}

        if not device:
            return {"error": "Network device not found"}

        # Get latest metrics
        metric = (
            db.query(NetworkMetric)
            .filter_by(device_id=device.id)
            .order_by(NetworkMetric.timestamp.desc())
            .first()
        )

        if not metric:
            return {"device": device.name, "message": "No metrics available for this device"}

        # Calculate traffic rates if we have previous metrics
        prev_metric = (
            db.query(NetworkMetric)
            .filter(
                NetworkMetric.device_id == device.id, NetworkMetric.timestamp < metric.timestamp
            )
            .order_by(NetworkMetric.timestamp.desc())
            .first()
        )

        rx_rate = None
        tx_rate = None
        if prev_metric and metric.total_rx_bytes and prev_metric.total_rx_bytes:
            time_diff = (metric.timestamp - prev_metric.timestamp).total_seconds()
            if time_diff > 0:
                rx_rate = (
                    (metric.total_rx_bytes - prev_metric.total_rx_bytes) / time_diff / 1000000
                )  # Mbps
                tx_rate = (metric.total_tx_bytes - prev_metric.total_tx_bytes) / time_diff / 1000000

        return {
            "device": device.name,
            "ip_address": device.ip_address,
            "device_type": device.device_type,
            "vendor": device.vendor,
            "status": device.status,
            "timestamp": metric.timestamp.isoformat() if metric.timestamp else None,
            "cpu_usage": metric.cpu_usage,
            "memory_usage": metric.memory_usage,
            "temperature": metric.temperature,
            "uptime_days": round(metric.uptime_seconds / 86400, 1)
            if metric.uptime_seconds
            else None,
            "total_rx_bytes": metric.total_rx_bytes,
            "total_tx_bytes": metric.total_tx_bytes,
            "rx_rate_mbps": round(rx_rate, 2) if rx_rate else None,
            "tx_rate_mbps": round(tx_rate, 2) if tx_rate else None,
            "total_errors": metric.total_errors,
        }
    finally:
        db.close()


async def get_port_status_handler(
    device_id: int = None,
    device_name: str = None,
    port_number: int = None,
) -> dict:
    """Get status of switch ports. If port_number not provided, returns all ports."""
    db = SessionLocal()
    try:
        # Find device
        if device_id:
            device = db.query(NetworkDevice).filter_by(id=device_id).first()
        elif device_name:
            device = db.query(NetworkDevice).filter_by(name=device_name).first()
        else:
            return {"error": "Must provide either device_id or device_name"}

        if not device:
            return {"error": "Network device not found"}

        # Get ports
        query = db.query(NetworkPort).filter_by(device_id=device.id)
        if port_number:
            query = query.filter_by(port_number=port_number)

        ports = query.order_by(NetworkPort.port_number).all()

        if not ports:
            if port_number:
                return {"error": f"Port {port_number} not found on device {device.name}"}
            return {"device": device.name, "message": "No ports found"}

        # Get latest metrics for traffic data
        metric = (
            db.query(NetworkMetric)
            .filter_by(device_id=device.id)
            .order_by(NetworkMetric.timestamp.desc())
            .first()
        )

        port_traffic = metric.port_metrics if metric and metric.port_metrics else {}

        return {
            "device": device.name,
            "ip_address": device.ip_address,
            "ports": [
                {
                    "port_number": p.port_number,
                    "port_name": p.port_name,
                    "enabled": p.enabled,
                    "link_status": p.link_status,
                    "speed": p.speed,
                    "vlan_id": p.vlan_id,
                    "vlan_name": p.vlan_name,
                    "poe_enabled": p.poe_enabled,
                    "poe_power_watts": p.poe_power,
                    "connected_mac": p.connected_mac,
                    "connected_device": p.connected_device,
                    "rx_bytes": port_traffic.get(str(p.if_index), {}).get("rx_bytes"),
                    "tx_bytes": port_traffic.get(str(p.if_index), {}).get("tx_bytes"),
                }
                for p in ports
            ],
            "total_ports": len(ports),
            "ports_up": len([p for p in ports if p.link_status == "up"]),
            "ports_down": len([p for p in ports if p.link_status == "down"]),
        }
    finally:
        db.close()


async def get_network_topology_handler() -> dict:
    """Get network topology showing device connections and relationships."""
    db = SessionLocal()
    try:
        devices = db.query(NetworkDevice).all()

        # Build topology from port connection data
        nodes = []
        links = []
        seen_macs = {}

        for device in devices:
            nodes.append(
                {
                    "id": f"device_{device.id}",
                    "name": device.name,
                    "type": device.device_type,
                    "ip": device.ip_address,
                    "status": device.status,
                }
            )

            # Track which MACs are on which ports for link detection
            ports = db.query(NetworkPort).filter_by(device_id=device.id).all()
            for port in ports:
                if port.connected_mac:
                    if port.connected_mac in seen_macs:
                        # Found a link between devices
                        links.append(
                            {
                                "source": f"device_{device.id}",
                                "target": seen_macs[port.connected_mac]["device_id"],
                                "source_port": port.port_number,
                                "target_port": seen_macs[port.connected_mac]["port_number"],
                            }
                        )
                    else:
                        seen_macs[port.connected_mac] = {
                            "device_id": f"device_{device.id}",
                            "port_number": port.port_number,
                        }

        return {
            "nodes": nodes,
            "links": links,
            "device_count": len(devices),
            "link_count": len(links),
        }
    finally:
        db.close()


async def get_network_device_history_handler(
    device_id: int = None,
    device_name: str = None,
    hours: int = 1,
) -> dict:
    """Get metric history for a network device over the specified time period."""
    db = SessionLocal()
    try:
        # Find device
        if device_id:
            device = db.query(NetworkDevice).filter_by(id=device_id).first()
        elif device_name:
            device = db.query(NetworkDevice).filter_by(name=device_name).first()
        else:
            return {"error": "Must provide either device_id or device_name"}

        if not device:
            return {"error": "Network device not found"}

        # Get metrics from the past N hours
        since = datetime.utcnow() - timedelta(hours=hours)
        metrics = (
            db.query(NetworkMetric)
            .filter(NetworkMetric.device_id == device.id, NetworkMetric.timestamp > since)
            .order_by(NetworkMetric.timestamp.desc())
            .limit(100)
            .all()
        )

        if not metrics:
            return {
                "device": device.name,
                "message": f"No metrics found in the last {hours} hour(s)",
            }

        # Calculate averages
        cpu_values = [m.cpu_usage for m in metrics if m.cpu_usage is not None]
        mem_values = [m.memory_usage for m in metrics if m.memory_usage is not None]
        temp_values = [m.temperature for m in metrics if m.temperature is not None]

        return {
            "device": device.name,
            "device_type": device.device_type,
            "period_hours": hours,
            "sample_count": len(metrics),
            "averages": {
                "cpu_usage": round(sum(cpu_values) / len(cpu_values), 1) if cpu_values else None,
                "memory_usage": round(sum(mem_values) / len(mem_values), 1) if mem_values else None,
                "temperature": round(sum(temp_values) / len(temp_values), 1)
                if temp_values
                else None,
            },
            "latest": {
                "timestamp": metrics[0].timestamp.isoformat() if metrics[0].timestamp else None,
                "cpu_usage": metrics[0].cpu_usage,
                "memory_usage": metrics[0].memory_usage,
                "temperature": metrics[0].temperature,
                "total_rx_bytes": metrics[0].total_rx_bytes,
                "total_tx_bytes": metrics[0].total_tx_bytes,
            },
        }
    finally:
        db.close()


# =============================================================================
# Tool Registrations
# =============================================================================

list_network_devices_tool = Tool(
    name="list_network_devices",
    description="Get a list of all monitored network devices (switches, routers, access points) with their current status, vendor, and location.",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    handler=list_network_devices_handler,
)

get_network_device_metrics_tool = Tool(
    name="get_network_device_metrics",
    description="Get current metrics (CPU, memory, temperature, traffic) for a specific network device. Provide either device_id or name.",
    parameters={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "integer",
                "description": "The network device ID",
            },
            "name": {
                "type": "string",
                "description": "The network device name",
            },
        },
        "required": [],
    },
    handler=get_network_device_metrics_handler,
)

get_port_status_tool = Tool(
    name="get_port_status",
    description="Get status of switch ports including link status, speed, VLAN, PoE power, and traffic. Can query a specific port or all ports.",
    parameters={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "integer",
                "description": "The network device ID",
            },
            "device_name": {
                "type": "string",
                "description": "The network device name",
            },
            "port_number": {
                "type": "integer",
                "description": "Specific port number to query (optional, omit for all ports)",
            },
        },
        "required": [],
    },
    handler=get_port_status_handler,
)

get_network_topology_tool = Tool(
    name="get_network_topology",
    description="Get the network topology showing device connections and relationships between switches, routers, and access points.",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    handler=get_network_topology_handler,
)

get_network_device_history_tool = Tool(
    name="get_network_device_history",
    description="Get metric history and averages for a network device over a time period. Defaults to last 1 hour.",
    parameters={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "integer",
                "description": "The network device ID",
            },
            "device_name": {
                "type": "string",
                "description": "The network device name",
            },
            "hours": {
                "type": "integer",
                "description": "Number of hours to look back (default: 1)",
            },
        },
        "required": [],
    },
    handler=get_network_device_history_handler,
)

# Register all tools
tool_registry.register(list_network_devices_tool)
tool_registry.register(get_network_device_metrics_tool)
tool_registry.register(get_port_status_tool)
tool_registry.register(get_network_topology_tool)
tool_registry.register(get_network_device_history_tool)
