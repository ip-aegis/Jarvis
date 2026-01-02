from app.tools.base import Tool, tool_registry
from app.database import SessionLocal
from app.models import Server, Metric
from datetime import datetime, timedelta


async def list_servers_handler() -> dict:
    """Get a list of all monitored servers with their status."""
    db = SessionLocal()
    try:
        servers = db.query(Server).all()
        return {
            "servers": [
                {
                    "id": s.id,
                    "hostname": s.hostname,
                    "ip_address": s.ip_address,
                    "status": s.status,
                    "os_info": s.os_info,
                    "cpu_info": s.cpu_info,
                    "cpu_cores": s.cpu_cores,
                    "memory_total": s.memory_total,
                    "gpu_info": s.gpu_info,
                    "agent_installed": s.agent_installed,
                }
                for s in servers
            ],
            "total": len(servers),
        }
    finally:
        db.close()


async def get_server_metrics_handler(server_id: int = None, hostname: str = None) -> dict:
    """Get current metrics for a specific server by ID or hostname."""
    db = SessionLocal()
    try:
        # Find server
        if server_id:
            server = db.query(Server).filter_by(id=server_id).first()
        elif hostname:
            server = db.query(Server).filter_by(hostname=hostname).first()
        else:
            return {"error": "Must provide either server_id or hostname"}

        if not server:
            return {"error": "Server not found"}

        # Get latest metrics
        metric = db.query(Metric).filter_by(
            server_id=server.id
        ).order_by(Metric.timestamp.desc()).first()

        if not metric:
            return {
                "server": server.hostname,
                "message": "No metrics available for this server"
            }

        return {
            "server": server.hostname,
            "ip_address": server.ip_address,
            "timestamp": metric.timestamp.isoformat() if metric.timestamp else None,
            "cpu_usage": metric.cpu_usage,
            "memory_percent": metric.memory_percent,
            "memory_used_gb": round(metric.memory_used / 1024 / 1024 / 1024, 2) if metric.memory_used else None,
            "memory_total_gb": round(metric.memory_total / 1024 / 1024 / 1024, 2) if metric.memory_total else None,
            "disk_percent": metric.disk_percent,
            "gpu_utilization": metric.gpu_utilization,
            "gpu_memory_percent": metric.gpu_memory_percent,
            "gpu_temperature": metric.gpu_temperature,
            "gpu_power": metric.gpu_power,
            "load_avg_1m": metric.load_avg_1m,
            "load_avg_5m": metric.load_avg_5m,
            "load_avg_15m": metric.load_avg_15m,
        }
    finally:
        db.close()


async def get_metric_history_handler(
    server_id: int = None,
    hostname: str = None,
    hours: int = 1
) -> dict:
    """Get metric history for a server over the specified time period."""
    db = SessionLocal()
    try:
        # Find server
        if server_id:
            server = db.query(Server).filter_by(id=server_id).first()
        elif hostname:
            server = db.query(Server).filter_by(hostname=hostname).first()
        else:
            return {"error": "Must provide either server_id or hostname"}

        if not server:
            return {"error": "Server not found"}

        # Get metrics from the past N hours
        since = datetime.utcnow() - timedelta(hours=hours)
        metrics = db.query(Metric).filter(
            Metric.server_id == server.id,
            Metric.timestamp > since
        ).order_by(Metric.timestamp.desc()).limit(100).all()

        if not metrics:
            return {
                "server": server.hostname,
                "message": f"No metrics found in the last {hours} hour(s)"
            }

        # Calculate averages
        cpu_avg = sum(m.cpu_usage or 0 for m in metrics) / len(metrics)
        mem_avg = sum(m.memory_percent or 0 for m in metrics) / len(metrics)
        gpu_avg = sum(m.gpu_utilization or 0 for m in metrics if m.gpu_utilization) / len([m for m in metrics if m.gpu_utilization]) if any(m.gpu_utilization for m in metrics) else None

        return {
            "server": server.hostname,
            "period_hours": hours,
            "sample_count": len(metrics),
            "averages": {
                "cpu_usage": round(cpu_avg, 1),
                "memory_percent": round(mem_avg, 1),
                "gpu_utilization": round(gpu_avg, 1) if gpu_avg else None,
            },
            "latest": {
                "timestamp": metrics[0].timestamp.isoformat() if metrics[0].timestamp else None,
                "cpu_usage": metrics[0].cpu_usage,
                "memory_percent": metrics[0].memory_percent,
                "gpu_utilization": metrics[0].gpu_utilization,
            },
        }
    finally:
        db.close()


# Register the tools
list_servers_tool = Tool(
    name="list_servers",
    description="Get a list of all monitored servers with their current status, hardware info, and agent status.",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    handler=list_servers_handler,
)

get_server_metrics_tool = Tool(
    name="get_server_metrics",
    description="Get current metrics (CPU, memory, disk, GPU) for a specific server. Provide either server_id or hostname.",
    parameters={
        "type": "object",
        "properties": {
            "server_id": {
                "type": "integer",
                "description": "The server ID",
            },
            "hostname": {
                "type": "string",
                "description": "The server hostname",
            },
        },
        "required": [],
    },
    handler=get_server_metrics_handler,
)

get_metric_history_tool = Tool(
    name="get_metric_history",
    description="Get metric history and averages for a server over a time period. Defaults to last 1 hour.",
    parameters={
        "type": "object",
        "properties": {
            "server_id": {
                "type": "integer",
                "description": "The server ID",
            },
            "hostname": {
                "type": "string",
                "description": "The server hostname",
            },
            "hours": {
                "type": "integer",
                "description": "Number of hours to look back (default: 1)",
            },
        },
        "required": [],
    },
    handler=get_metric_history_handler,
)

# Register all tools
tool_registry.register(list_servers_tool)
tool_registry.register(get_server_metrics_tool)
tool_registry.register(get_metric_history_tool)
