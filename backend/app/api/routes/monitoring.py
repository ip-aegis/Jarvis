from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import asyncio
import json

from app.database import get_db
from app.models import Server, Metric

router = APIRouter()


class AgentCPU(BaseModel):
    usage: Optional[float] = None
    per_core: Optional[Dict[str, float]] = None  # {"cpu0": 25.5, "cpu1": 35.2, ...}

class AgentMemory(BaseModel):
    total: Optional[float] = None
    used: Optional[float] = None
    available: Optional[float] = None
    buffers: Optional[float] = None
    cached: Optional[float] = None
    percent: Optional[float] = None
    swap_total: Optional[float] = None
    swap_used: Optional[float] = None

class AgentDisk(BaseModel):
    total: Optional[float] = None
    used: Optional[float] = None
    percent: Optional[float] = None

class AgentGPU(BaseModel):
    utilization: Optional[float] = None
    memory_used: Optional[float] = None
    memory_total: Optional[float] = None
    memory_percent: Optional[float] = None
    temperature: Optional[float] = None
    power: Optional[float] = None

class AgentLoadAvg(BaseModel):
    one_m: Optional[float] = None
    five_m: Optional[float] = None
    fifteen_m: Optional[float] = None

    class Config:
        # Allow field aliases for 1m, 5m, 15m
        populate_by_name = True

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, dict):
            return cls(
                one_m=v.get("1m"),
                five_m=v.get("5m"),
                fifteen_m=v.get("15m")
            )
        return v

class MetricReport(BaseModel):
    server_id: int
    timestamp: Optional[str] = None
    hostname: Optional[str] = None
    cpu: Optional[AgentCPU] = None
    memory: Optional[AgentMemory] = None
    disk: Optional[AgentDisk] = None
    gpu: Optional[AgentGPU] = None
    load_avg: Optional[Dict[str, float]] = None  # {"1m": 1.5, "5m": 2.1, "15m": 1.8}
    temperatures: Optional[Dict[str, float]] = None


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[WebSocket, List[int]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = []

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]

    def subscribe(self, websocket: WebSocket, server_ids: List[int]):
        self.subscriptions[websocket] = server_ids

    async def broadcast(self, message: dict):
        """Broadcast to all connections or only those subscribed to the server."""
        server_id = message.get("server_id")
        for connection in self.active_connections:
            try:
                subscribed = self.subscriptions.get(connection, [])
                # Send if no subscriptions (send all) or if subscribed to this server
                if not subscribed or server_id in subscribed:
                    await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@router.get("/")
async def get_all_metrics(db: Session = Depends(get_db)):
    """Get current metrics for all servers."""
    servers = db.query(Server).all()
    metrics = []

    for server in servers:
        # Get the most recent metric for each server
        latest = (
            db.query(Metric)
            .filter(Metric.server_id == server.id)
            .order_by(desc(Metric.timestamp))
            .first()
        )

        metrics.append({
            "server_id": server.id,
            "hostname": server.hostname,
            "ip_address": server.ip_address,
            "status": server.status,
            "cpu_usage": latest.cpu_usage if latest else None,
            "memory_percent": latest.memory_percent if latest else None,
            "disk_percent": latest.disk_percent if latest else None,
            "gpu_utilization": latest.gpu_utilization if latest else None,
            "gpu_temperature": latest.gpu_temperature if latest else None,
            "last_updated": latest.timestamp.isoformat() if latest else None,
        })

    return {"metrics": metrics}


@router.get("/{server_id}")
async def get_server_metrics(server_id: int, db: Session = Depends(get_db)):
    """Get current metrics for a specific server."""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    latest = (
        db.query(Metric)
        .filter(Metric.server_id == server_id)
        .order_by(desc(Metric.timestamp))
        .first()
    )

    if not latest:
        return {
            "server_id": server_id,
            "hostname": server.hostname,
            "status": server.status,
            "cpu": {"usage": 0, "cores": server.cpu_cores or 0, "per_core": {}},
            "memory": {"used": 0, "total": 0, "percent": 0, "available": 0, "buffers": 0, "cached": 0},
            "swap": {"used": 0, "total": 0},
            "disk": {"used": 0, "total": 0, "percent": 0},
            "gpu": None,
            "load_avg": {"1m": 0, "5m": 0, "15m": 0},
            "temperatures": {},
            "last_updated": None,
        }

    return {
        "server_id": server_id,
        "hostname": server.hostname,
        "status": server.status,
        "cpu": {
            "usage": latest.cpu_usage,
            "cores": server.cpu_cores or 0,
            "per_core": latest.cpu_per_core or {},
        },
        "memory": {
            "used": latest.memory_used,
            "total": latest.memory_total,
            "percent": latest.memory_percent,
            "available": latest.memory_available,
            "buffers": latest.memory_buffers,
            "cached": latest.memory_cached,
        },
        "swap": {
            "used": latest.swap_used,
            "total": latest.swap_total,
        },
        "disk": {
            "used": latest.disk_used,
            "total": latest.disk_total,
            "percent": latest.disk_percent,
        },
        "gpu": {
            "utilization": latest.gpu_utilization,
            "memory_used": latest.gpu_memory_used,
            "memory_total": latest.gpu_memory_total,
            "memory_percent": latest.gpu_memory_percent,
            "temperature": latest.gpu_temperature,
            "power": latest.gpu_power,
        } if latest.gpu_utilization is not None else None,
        "load_avg": {
            "1m": latest.load_avg_1m,
            "5m": latest.load_avg_5m,
            "15m": latest.load_avg_15m,
        },
        "temperatures": latest.temperatures or {},
        "last_updated": latest.timestamp.isoformat(),
    }


@router.get("/{server_id}/history")
async def get_metrics_history(
    server_id: int,
    metric: str = "cpu",
    hours: int = 24,
    db: Session = Depends(get_db),
):
    """Get historical metrics for a server."""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    since = datetime.utcnow() - timedelta(hours=hours)

    metrics = (
        db.query(Metric)
        .filter(Metric.server_id == server_id, Metric.timestamp >= since)
        .order_by(Metric.timestamp)
        .all()
    )

    # Extract the requested metric
    data = []
    for m in metrics:
        value = None
        if metric == "cpu":
            value = m.cpu_usage
        elif metric == "memory":
            value = m.memory_percent
        elif metric == "disk":
            value = m.disk_percent
        elif metric == "gpu":
            value = m.gpu_utilization
        elif metric == "gpu_temp":
            value = m.gpu_temperature
        elif metric == "gpu_power":
            value = m.gpu_power

        if value is not None:
            data.append({
                "timestamp": m.timestamp.isoformat(),
                "value": value,
            })

    return {"data": data, "metric": metric, "hours": hours}


@router.websocket("/ws")
async def websocket_metrics(websocket: WebSocket):
    """WebSocket endpoint for real-time metrics streaming."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("action") == "subscribe":
                server_ids = message.get("server_ids", [])
                manager.subscribe(websocket, server_ids)
                await websocket.send_json({
                    "type": "subscribed",
                    "server_ids": server_ids,
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.post("/agent/report")
async def receive_agent_report(report: MetricReport, db: Session = Depends(get_db)):
    """Receive metrics report from a monitoring agent."""
    # Verify server exists
    server = db.query(Server).filter(Server.id == report.server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    # Update server status to online
    server.status = "online"

    # Extract values from nested structure
    cpu_usage = report.cpu.usage if report.cpu else None
    cpu_per_core = report.cpu.per_core if report.cpu else None
    memory_used = report.memory.used if report.memory else None
    memory_total = report.memory.total if report.memory else None
    memory_percent = report.memory.percent if report.memory else None
    memory_available = report.memory.available if report.memory else None
    memory_buffers = report.memory.buffers if report.memory else None
    memory_cached = report.memory.cached if report.memory else None
    swap_used = report.memory.swap_used if report.memory else None
    swap_total = report.memory.swap_total if report.memory else None
    disk_used = report.disk.used if report.disk else None
    disk_total = report.disk.total if report.disk else None
    disk_percent = report.disk.percent if report.disk else None
    gpu_utilization = report.gpu.utilization if report.gpu else None
    gpu_memory_used = report.gpu.memory_used if report.gpu else None
    gpu_memory_total = report.gpu.memory_total if report.gpu else None
    gpu_memory_percent = report.gpu.memory_percent if report.gpu else None
    gpu_temperature = report.gpu.temperature if report.gpu else None
    gpu_power = report.gpu.power if report.gpu else None
    load_avg_1m = report.load_avg.get("1m") if report.load_avg else None
    load_avg_5m = report.load_avg.get("5m") if report.load_avg else None
    load_avg_15m = report.load_avg.get("15m") if report.load_avg else None

    # Create metric record
    metric = Metric(
        server_id=report.server_id,
        cpu_usage=cpu_usage,
        cpu_per_core=cpu_per_core,
        memory_used=memory_used,
        memory_total=memory_total,
        memory_percent=memory_percent,
        memory_available=memory_available,
        memory_buffers=memory_buffers,
        memory_cached=memory_cached,
        swap_used=swap_used,
        swap_total=swap_total,
        disk_used=disk_used,
        disk_total=disk_total,
        disk_percent=disk_percent,
        gpu_utilization=gpu_utilization,
        gpu_memory_used=gpu_memory_used,
        gpu_memory_total=gpu_memory_total,
        gpu_memory_percent=gpu_memory_percent,
        gpu_temperature=gpu_temperature,
        gpu_power=gpu_power,
        load_avg_1m=load_avg_1m,
        load_avg_5m=load_avg_5m,
        load_avg_15m=load_avg_15m,
        temperatures=report.temperatures,
    )
    db.add(metric)
    db.commit()

    # Broadcast to WebSocket clients
    broadcast_data = {
        "type": "metric",
        "server_id": report.server_id,
        "hostname": server.hostname,
        "cpu_usage": cpu_usage,
        "cpu_per_core": cpu_per_core,
        "memory_percent": memory_percent,
        "disk_percent": disk_percent,
        "gpu_utilization": gpu_utilization,
        "gpu_memory_percent": gpu_memory_percent,
        "gpu_temperature": gpu_temperature,
        "gpu_power": gpu_power,
        "load_avg": report.load_avg,
        "timestamp": datetime.utcnow().isoformat(),
    }
    await manager.broadcast(broadcast_data)

    return {"status": "received"}
