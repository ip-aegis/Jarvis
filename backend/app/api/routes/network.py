"""
Network device management API routes.
Supports switches, routers, firewalls, and access points.
"""
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database import get_db
from app.models import NetworkDevice, NetworkMetric, NetworkPort
from app.services.ollama import OllamaService
from app.services.snmp import SNMPCredentials, SNMPService

logger = get_logger(__name__)

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class SNMPConfig(BaseModel):
    """SNMP connection configuration."""

    version: str = "2c"  # "2c" or "3"
    community: Optional[str] = "public"  # For v2c
    # For v3
    username: Optional[str] = None
    auth_protocol: Optional[str] = None  # MD5, SHA
    auth_password: Optional[str] = None
    priv_protocol: Optional[str] = None  # DES, AES
    priv_password: Optional[str] = None


class NetworkDeviceOnboardRequest(BaseModel):
    """Request to onboard a new network device."""

    name: str
    ip_address: str
    device_type: str = Field(..., description="switch, router, firewall, access_point")
    connection_type: str = "snmp"  # snmp, ssh, rest_api
    snmp_config: Optional[SNMPConfig] = None
    location: Optional[str] = None
    description: Optional[str] = None


class NetworkDeviceResponse(BaseModel):
    """Network device response model."""

    id: int
    name: str
    ip_address: str
    mac_address: Optional[str] = None
    device_type: str
    vendor: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    connection_type: str
    location: Optional[str] = None
    description: Optional[str] = None
    port_count: Optional[int] = None
    poe_capable: bool = False
    status: str
    last_seen: Optional[datetime] = None
    uptime_seconds: Optional[int] = None

    class Config:
        from_attributes = True


class NetworkPortResponse(BaseModel):
    """Network port response model."""

    id: int
    port_number: int
    port_name: Optional[str] = None
    enabled: bool = True
    speed: Optional[str] = None
    duplex: Optional[str] = None
    vlan_id: Optional[int] = None
    vlan_name: Optional[str] = None
    poe_enabled: bool = False
    poe_power: Optional[float] = None
    link_status: Optional[str] = None
    admin_status: Optional[str] = None
    connected_mac: Optional[str] = None
    connected_device: Optional[str] = None

    class Config:
        from_attributes = True


class NetworkMetricsResponse(BaseModel):
    """Network metrics response model."""

    device_id: int
    device_name: str
    timestamp: datetime
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    temperature: Optional[float] = None
    uptime_seconds: Optional[int] = None
    total_rx_bytes: Optional[int] = None
    total_tx_bytes: Optional[int] = None
    port_metrics: Optional[dict[str, Any]] = None


class DiscoveryRequest(BaseModel):
    """Request to discover devices on a network."""

    ip_addresses: list[str]
    snmp_config: SNMPConfig


# =============================================================================
# Device Management Endpoints
# =============================================================================


@router.get("/devices")
async def list_network_devices(db: Session = Depends(get_db)):
    """List all registered network devices."""
    devices = db.query(NetworkDevice).all()
    return {"devices": [NetworkDeviceResponse.model_validate(d) for d in devices]}


@router.post("/devices/onboard")
async def onboard_network_device(
    request: NetworkDeviceOnboardRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Onboard a new network device:
    1. Test SNMP connectivity
    2. Discover device information
    3. Get interface/port information
    4. Save to database
    5. Generate LLM analysis
    """
    # Check if device already exists
    existing = (
        db.query(NetworkDevice).filter(NetworkDevice.ip_address == request.ip_address).first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Device with this IP already exists")

    snmp_service = SNMPService()

    # Build credentials from request
    snmp_config = request.snmp_config or SNMPConfig()
    credentials = SNMPCredentials(
        version=snmp_config.version,
        community=snmp_config.community or "public",
        username=snmp_config.username,
        auth_protocol=snmp_config.auth_protocol,
        auth_password=snmp_config.auth_password,
        priv_protocol=snmp_config.priv_protocol,
        priv_password=snmp_config.priv_password,
    )

    try:
        # Step 1: Test connectivity
        success, message = await snmp_service.test_connectivity(request.ip_address, credentials)
        if not success:
            raise HTTPException(status_code=400, detail=f"Cannot connect to device: {message}")

        # Step 2: Discover device info
        discovery = await snmp_service.discover_device(request.ip_address, credentials)
        if not discovery:
            raise HTTPException(status_code=400, detail="Failed to discover device")

        system_info = discovery["system_info"]

        # Step 3: Get interface information
        interfaces = await snmp_service.get_interfaces(request.ip_address, credentials)

        # Step 4: Save device to database
        device = NetworkDevice(
            name=request.name,
            ip_address=request.ip_address,
            device_type=request.device_type or discovery["device_type"],
            vendor=system_info.get("vendor"),
            model=None,  # Would need Entity MIB parsing
            firmware_version=None,
            connection_type=request.connection_type,
            snmp_community=snmp_config.community if snmp_config.version == "2c" else None,
            snmp_version=snmp_config.version,
            snmp_v3_config={
                "username": snmp_config.username,
                "auth_protocol": snmp_config.auth_protocol,
                "priv_protocol": snmp_config.priv_protocol,
            }
            if snmp_config.version == "3"
            else None,
            location=request.location or system_info.get("location"),
            description=request.description or system_info.get("description"),
            port_count=len(interfaces),
            status="online",
            last_seen=datetime.utcnow(),
            uptime_seconds=int(system_info.get("uptime_seconds", 0)),
        )
        db.add(device)
        db.commit()
        db.refresh(device)

        # Step 5: Save port information
        for iface in interfaces:
            # Filter to physical ports (skip VLANs, management interfaces, etc.)
            name = iface.get("name", "").lower()
            if any(skip in name for skip in ["vlan", "null", "loopback", "cpu"]):
                continue

            port = NetworkPort(
                device_id=device.id,
                port_number=iface["if_index"],
                port_name=iface.get("name"),
                if_index=iface["if_index"],
                enabled=iface.get("admin_status") == "enabled",
                speed=f"{iface.get('speed_mbps', 0)}M" if iface.get("speed_mbps") else None,
                link_status=iface.get("oper_status"),
                admin_status=iface.get("admin_status"),
            )
            db.add(port)

        db.commit()

        # Step 6: Collect initial metrics
        background_tasks.add_task(
            collect_device_metrics,
            device.id,
            request.ip_address,
            credentials,
        )

        # Step 7: Generate LLM analysis
        llm_analysis = None
        try:
            ollama = OllamaService()
            analysis_prompt = f"""Analyze this network device and provide a brief summary for a network administrator.

Device Information:
- Name: {request.name}
- IP Address: {request.ip_address}
- Type: {request.device_type}
- Vendor: {system_info.get('vendor', 'Unknown')}
- Description: {system_info.get('description', 'N/A')[:200]}
- Location: {system_info.get('location', 'Not set')}
- Interface Count: {len(interfaces)}
- Uptime: {system_info.get('uptime_seconds', 0) / 86400:.1f} days

Please provide:
1. **Device Profile**: What role does this device likely serve in the network?
2. **Key Details**: Notable capabilities or configuration points
3. **Monitoring Tips**: 2-3 things to watch for this device type

Keep the response concise (under 150 words) and practical."""

            llm_analysis = await ollama.generate(analysis_prompt)
        except Exception as e:
            llm_analysis = f"Analysis unavailable: {str(e)}"

        return {
            "status": "success",
            "device_id": device.id,
            "name": device.name,
            "ip_address": device.ip_address,
            "device_type": device.device_type,
            "vendor": device.vendor,
            "port_count": device.port_count,
            "system_info": system_info,
            "llm_analysis": llm_analysis,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "network_device_onboarding_failed",
            name=request.name,
            ip_address=request.ip_address,
        )
        raise HTTPException(status_code=500, detail=f"Onboarding failed: {str(e)}")


@router.get("/devices/{device_id}")
async def get_network_device(device_id: int, db: Session = Depends(get_db)):
    """Get details for a specific network device."""
    device = db.query(NetworkDevice).filter(NetworkDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return NetworkDeviceResponse.model_validate(device)


@router.delete("/devices/{device_id}")
async def remove_network_device(device_id: int, db: Session = Depends(get_db)):
    """Remove a network device from monitoring."""
    device = db.query(NetworkDevice).filter(NetworkDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    db.delete(device)
    db.commit()
    return {"status": "deleted", "device_id": device_id}


@router.post("/devices/{device_id}/test")
async def test_device_connection(device_id: int, db: Session = Depends(get_db)):
    """Test SNMP connection to a network device."""
    device = db.query(NetworkDevice).filter(NetworkDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    snmp_service = SNMPService()
    credentials = _get_credentials_for_device(device)

    success, message = await snmp_service.test_connectivity(device.ip_address, credentials)

    if success:
        device.status = "online"
        device.last_seen = datetime.utcnow()
        db.commit()
        return {"status": "connected", "device_id": device_id, "message": message}
    else:
        device.status = "offline"
        db.commit()
        return {"status": "failed", "device_id": device_id, "error": message}


# =============================================================================
# Port Management Endpoints
# =============================================================================


@router.get("/devices/{device_id}/ports")
async def get_device_ports(device_id: int, db: Session = Depends(get_db)):
    """Get all ports for a network device."""
    device = db.query(NetworkDevice).filter(NetworkDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    ports = db.query(NetworkPort).filter(NetworkPort.device_id == device_id).all()
    return {"device_id": device_id, "ports": [NetworkPortResponse.model_validate(p) for p in ports]}


@router.post("/devices/{device_id}/ports/refresh")
async def refresh_device_ports(device_id: int, db: Session = Depends(get_db)):
    """Refresh port information from the device."""
    device = db.query(NetworkDevice).filter(NetworkDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    snmp_service = SNMPService()
    credentials = _get_credentials_for_device(device)

    try:
        interfaces = await snmp_service.get_interfaces(device.ip_address, credentials)
        traffic = await snmp_service.get_interface_traffic(device.ip_address, credentials)

        # Update existing ports or create new ones
        for iface in interfaces:
            if_index = iface["if_index"]
            port = (
                db.query(NetworkPort)
                .filter(NetworkPort.device_id == device_id, NetworkPort.if_index == if_index)
                .first()
            )

            traffic_data = traffic.get(if_index, {})

            if port:
                port.port_name = iface.get("name")
                port.enabled = iface.get("admin_status") == "enabled"
                port.speed = f"{iface.get('speed_mbps', 0)}M" if iface.get("speed_mbps") else None
                port.link_status = iface.get("oper_status")
                port.admin_status = iface.get("admin_status")
            else:
                name = iface.get("name", "").lower()
                if any(skip in name for skip in ["vlan", "null", "loopback", "cpu"]):
                    continue

                port = NetworkPort(
                    device_id=device_id,
                    port_number=if_index,
                    port_name=iface.get("name"),
                    if_index=if_index,
                    enabled=iface.get("admin_status") == "enabled",
                    speed=f"{iface.get('speed_mbps', 0)}M" if iface.get("speed_mbps") else None,
                    link_status=iface.get("oper_status"),
                    admin_status=iface.get("admin_status"),
                )
                db.add(port)

        device.last_seen = datetime.utcnow()
        db.commit()

        ports = db.query(NetworkPort).filter(NetworkPort.device_id == device_id).all()
        return {
            "status": "refreshed",
            "device_id": device_id,
            "port_count": len(ports),
            "ports": [NetworkPortResponse.model_validate(p) for p in ports],
        }

    except Exception as e:
        logger.exception("port_refresh_failed", device_id=device_id)
        raise HTTPException(status_code=500, detail=f"Failed to refresh ports: {str(e)}")


# =============================================================================
# Metrics Endpoints
# =============================================================================


@router.get("/metrics")
async def get_all_network_metrics(db: Session = Depends(get_db)):
    """Get latest metrics for all network devices."""
    devices = db.query(NetworkDevice).all()
    results = []

    for device in devices:
        latest_metric = (
            db.query(NetworkMetric)
            .filter(NetworkMetric.device_id == device.id)
            .order_by(NetworkMetric.timestamp.desc())
            .first()
        )

        if latest_metric:
            results.append(
                {
                    "device_id": device.id,
                    "device_name": device.name,
                    "timestamp": latest_metric.timestamp,
                    "cpu_usage": latest_metric.cpu_usage,
                    "memory_usage": latest_metric.memory_usage,
                    "temperature": latest_metric.temperature,
                    "uptime_seconds": latest_metric.uptime_seconds,
                    "total_rx_bytes": latest_metric.total_rx_bytes,
                    "total_tx_bytes": latest_metric.total_tx_bytes,
                }
            )
        else:
            results.append(
                {
                    "device_id": device.id,
                    "device_name": device.name,
                    "timestamp": None,
                    "message": "No metrics available",
                }
            )

    return {"metrics": results}


@router.get("/metrics/{device_id}")
async def get_device_metrics(device_id: int, db: Session = Depends(get_db)):
    """Get current metrics for a specific network device."""
    device = db.query(NetworkDevice).filter(NetworkDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    latest_metric = (
        db.query(NetworkMetric)
        .filter(NetworkMetric.device_id == device_id)
        .order_by(NetworkMetric.timestamp.desc())
        .first()
    )

    if not latest_metric:
        return {
            "device_id": device_id,
            "device_name": device.name,
            "message": "No metrics available",
        }

    return {
        "device_id": device_id,
        "device_name": device.name,
        "timestamp": latest_metric.timestamp,
        "cpu_usage": latest_metric.cpu_usage,
        "memory_usage": latest_metric.memory_usage,
        "temperature": latest_metric.temperature,
        "uptime_seconds": latest_metric.uptime_seconds,
        "total_rx_bytes": latest_metric.total_rx_bytes,
        "total_tx_bytes": latest_metric.total_tx_bytes,
        "port_metrics": latest_metric.port_metrics,
    }


@router.post("/metrics/{device_id}/collect")
async def trigger_metrics_collection(
    device_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Manually trigger metrics collection for a device."""
    device = db.query(NetworkDevice).filter(NetworkDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    credentials = _get_credentials_for_device(device)
    background_tasks.add_task(collect_device_metrics, device_id, device.ip_address, credentials)

    return {"status": "collection_triggered", "device_id": device_id}


@router.get("/metrics/{device_id}/history")
async def get_device_metrics_history(
    device_id: int,
    hours: int = 24,
    db: Session = Depends(get_db),
):
    """Get historical metrics for a network device."""
    device = db.query(NetworkDevice).filter(NetworkDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    from datetime import timedelta

    since = datetime.utcnow() - timedelta(hours=hours)

    metrics = (
        db.query(NetworkMetric)
        .filter(NetworkMetric.device_id == device_id, NetworkMetric.timestamp >= since)
        .order_by(NetworkMetric.timestamp.asc())
        .all()
    )

    return {
        "device_id": device_id,
        "device_name": device.name,
        "hours": hours,
        "metrics": [
            {
                "timestamp": m.timestamp,
                "cpu_usage": m.cpu_usage,
                "memory_usage": m.memory_usage,
                "temperature": m.temperature,
                "total_rx_bytes": m.total_rx_bytes,
                "total_tx_bytes": m.total_tx_bytes,
            }
            for m in metrics
        ],
    }


# =============================================================================
# Discovery Endpoints
# =============================================================================


@router.post("/discover")
async def discover_devices(request: DiscoveryRequest, db: Session = Depends(get_db)):
    """Scan a list of IP addresses for SNMP-enabled devices."""
    snmp_service = SNMPService()
    credentials = SNMPCredentials(
        version=request.snmp_config.version,
        community=request.snmp_config.community or "public",
        username=request.snmp_config.username,
        auth_protocol=request.snmp_config.auth_protocol,
        auth_password=request.snmp_config.auth_password,
        priv_protocol=request.snmp_config.priv_protocol,
        priv_password=request.snmp_config.priv_password,
    )

    discovered = []
    for ip in request.ip_addresses:
        try:
            device_info = await snmp_service.discover_device(ip, credentials)
            if device_info:
                # Check if already registered
                existing = db.query(NetworkDevice).filter(NetworkDevice.ip_address == ip).first()

                discovered.append(
                    {
                        "ip_address": ip,
                        "device_type": device_info["device_type"],
                        "vendor": device_info["vendor"],
                        "name": device_info["system_info"].get("name", ip),
                        "description": device_info["system_info"].get("description", "")[:200],
                        "interface_count": device_info["interface_count"],
                        "already_registered": existing is not None,
                    }
                )
        except Exception as e:
            logger.debug("discovery_failed", ip=ip, error=str(e))

    return {"discovered": discovered, "total": len(discovered)}


# =============================================================================
# Helper Functions
# =============================================================================


def _get_credentials_for_device(device: NetworkDevice) -> SNMPCredentials:
    """Build SNMP credentials from a device's stored configuration."""
    if device.snmp_version == "3" and device.snmp_v3_config:
        return SNMPCredentials(
            version="3",
            username=device.snmp_v3_config.get("username"),
            auth_protocol=device.snmp_v3_config.get("auth_protocol"),
            auth_password=device.snmp_v3_config.get("auth_password"),
            priv_protocol=device.snmp_v3_config.get("priv_protocol"),
            priv_password=device.snmp_v3_config.get("priv_password"),
        )
    else:
        return SNMPCredentials(
            version="2c",
            community=device.snmp_community or "public",
        )


async def collect_device_metrics(device_id: int, ip_address: str, credentials: SNMPCredentials):
    """Background task to collect metrics from a device."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        snmp_service = SNMPService()

        # Get system info for uptime
        system_info = await snmp_service.get_system_info(ip_address, credentials)

        # Get interface traffic
        traffic = await snmp_service.get_interface_traffic(ip_address, credentials)

        # Calculate totals
        total_rx = sum(t.get("rx_bytes", 0) for t in traffic.values())
        total_tx = sum(t.get("tx_bytes", 0) for t in traffic.values())
        total_errors = sum(t.get("rx_errors", 0) + t.get("tx_errors", 0) for t in traffic.values())

        # Try to get Cisco-specific CPU/memory (may fail on non-Cisco devices)
        cpu_usage = None
        memory_usage = None
        temperature = None

        if system_info.get("vendor") == "cisco":
            try:
                cisco_stats = await snmp_service.get_cisco_cpu_memory(ip_address, credentials)
                cpu_usage = cisco_stats.get("cpu_5min")
                memory_usage = cisco_stats.get("memory_percent")

                temps = await snmp_service.get_cisco_temperature(ip_address, credentials)
                if temps:
                    temperature = temps[0].get("temperature")
            except Exception:
                pass

        # Save metric
        metric = NetworkMetric(
            device_id=device_id,
            timestamp=datetime.utcnow(),
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            temperature=temperature,
            uptime_seconds=int(system_info.get("uptime_seconds", 0)),
            total_rx_bytes=total_rx,
            total_tx_bytes=total_tx,
            total_errors=total_errors,
            port_metrics={str(k): v for k, v in traffic.items()},
        )
        db.add(metric)

        # Update device status
        device = db.query(NetworkDevice).filter(NetworkDevice.id == device_id).first()
        if device:
            device.status = "online"
            device.last_seen = datetime.utcnow()
            device.uptime_seconds = int(system_info.get("uptime_seconds", 0))

        db.commit()
        logger.info("metrics_collected", device_id=device_id, ip=ip_address)

    except Exception as e:
        logger.error("metrics_collection_failed", device_id=device_id, error=str(e))
    finally:
        db.close()
