from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Server, Project, Metric

router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get summary statistics for the dashboard."""
    # Count servers
    total_servers = db.query(Server).count()
    online_servers = db.query(Server).filter_by(status="online").count()

    # Count projects
    total_projects = db.query(Project).count()

    # Count alerts (servers with high resource usage in last 5 minutes)
    five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
    alerts = 0

    # Check for high CPU usage (>90%)
    high_cpu = db.query(Metric).filter(
        Metric.timestamp > five_minutes_ago,
        Metric.cpu_usage > 90
    ).distinct(Metric.server_id).count()

    # Check for high memory usage (>90%)
    high_memory = db.query(Metric).filter(
        Metric.timestamp > five_minutes_ago,
        Metric.memory_percent > 90
    ).distinct(Metric.server_id).count()

    # Check for high disk usage (>90%)
    high_disk = db.query(Metric).filter(
        Metric.timestamp > five_minutes_ago,
        Metric.disk_percent > 90
    ).distinct(Metric.server_id).count()

    # Check for high GPU temperature (>85C)
    high_gpu_temp = db.query(Metric).filter(
        Metric.timestamp > five_minutes_ago,
        Metric.gpu_temperature > 85
    ).distinct(Metric.server_id).count()

    alerts = high_cpu + high_memory + high_disk + high_gpu_temp

    return {
        "servers": total_servers,
        "online": online_servers,
        "projects": total_projects,
        "alerts": alerts,
    }


@router.get("/activity")
async def get_recent_activity(db: Session = Depends(get_db), limit: int = 10):
    """Get recent activity for the dashboard."""
    activities = []

    # Get recently added servers
    recent_servers = db.query(Server).order_by(Server.created_at.desc()).limit(5).all()
    for server in recent_servers:
        activities.append({
            "type": "server_added",
            "message": f"Server '{server.hostname}' added",
            "timestamp": server.created_at.isoformat() if server.created_at else None,
            "icon": "server",
        })

    # Get recently scanned projects
    recent_projects = db.query(Project).filter(
        Project.last_scanned.isnot(None)
    ).order_by(Project.last_scanned.desc()).limit(5).all()
    for project in recent_projects:
        activities.append({
            "type": "project_scanned",
            "message": f"Project '{project.name}' scanned",
            "timestamp": project.last_scanned.isoformat() if project.last_scanned else None,
            "icon": "folder",
        })

    # Get servers with recent alerts
    five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
    alert_metrics = db.query(Metric).filter(
        Metric.timestamp > five_minutes_ago,
        (Metric.cpu_usage > 90) | (Metric.memory_percent > 90) | (Metric.gpu_temperature > 85)
    ).order_by(Metric.timestamp.desc()).limit(5).all()

    for metric in alert_metrics:
        server = db.query(Server).filter_by(id=metric.server_id).first()
        if server:
            alert_type = []
            if metric.cpu_usage and metric.cpu_usage > 90:
                alert_type.append(f"CPU {metric.cpu_usage:.1f}%")
            if metric.memory_percent and metric.memory_percent > 90:
                alert_type.append(f"Memory {metric.memory_percent:.1f}%")
            if metric.gpu_temperature and metric.gpu_temperature > 85:
                alert_type.append(f"GPU Temp {metric.gpu_temperature:.0f}C")

            activities.append({
                "type": "alert",
                "message": f"Alert on '{server.hostname}': {', '.join(alert_type)}",
                "timestamp": metric.timestamp.isoformat() if metric.timestamp else None,
                "icon": "alert",
            })

    # Sort by timestamp and limit
    activities.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    return {"activities": activities[:limit]}
