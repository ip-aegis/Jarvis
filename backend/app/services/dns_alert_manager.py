"""
DNS Alert Manager.

Manages real-time WebSocket connections for DNS security alerts.
"""

import asyncio
from typing import Optional

import structlog
from fastapi import WebSocket

from app.models import DnsSecurityAlert

logger = structlog.get_logger()


class DnsAlertManager:
    """Manages WebSocket connections for real-time DNS alerts."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.subscriptions: dict[WebSocket, dict] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
            # Default subscription: high and critical alerts
            self.subscriptions[websocket] = {
                "severity": ["high", "critical"],
                "alert_types": None,  # All types
                "client_ips": None,  # All clients
            }
        logger.info("websocket_connected", total_connections=len(self.active_connections))

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
            if websocket in self.subscriptions:
                del self.subscriptions[websocket]
        logger.info("websocket_disconnected", total_connections=len(self.active_connections))

    async def subscribe(self, websocket: WebSocket, filters: dict):
        """
        Update subscription filters for a connection.

        Filters can include:
        - severity: list of severity levels to receive
        - alert_types: list of alert types to receive
        - client_ips: list of client IPs to filter on
        """
        async with self._lock:
            if websocket in self.subscriptions:
                self.subscriptions[websocket].update(filters)
                logger.info("subscription_updated", filters=filters)

    async def broadcast_alert(self, alert: DnsSecurityAlert):
        """Broadcast alert to all subscribed connections."""
        alert_data = {
            "type": "dns_alert",
            "alert_id": str(alert.alert_id),
            "severity": alert.severity,
            "alert_type": alert.alert_type,
            "client_ip": alert.client_ip,
            "domain": alert.domain,
            "title": alert.title,
            "description": alert.description,
            "timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
            "status": alert.status,
        }

        disconnected = []

        for connection in self.active_connections:
            if self._should_send(connection, alert):
                try:
                    await connection.send_json(alert_data)
                except Exception as e:
                    logger.warning("websocket_send_failed", error=str(e))
                    disconnected.append(connection)

        # Clean up disconnected connections
        for conn in disconnected:
            await self.disconnect(conn)

    def _should_send(self, websocket: WebSocket, alert: DnsSecurityAlert) -> bool:
        """Check if alert should be sent to this connection based on subscription."""
        prefs = self.subscriptions.get(websocket, {})

        # Check severity filter
        severity_filter = prefs.get("severity")
        if severity_filter and alert.severity not in severity_filter:
            return False

        # Check alert type filter
        type_filter = prefs.get("alert_types")
        if type_filter and alert.alert_type not in type_filter:
            return False

        # Check client IP filter
        ip_filter = prefs.get("client_ips")
        if ip_filter and alert.client_ip not in ip_filter:
            return False

        return True

    async def send_personal(self, websocket: WebSocket, data: dict):
        """Send data to a specific connection."""
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.warning("websocket_send_failed", error=str(e))
            await self.disconnect(websocket)

    def get_connection_count(self) -> int:
        """Get number of active connections."""
        return len(self.active_connections)


# Singleton instance
_alert_manager: Optional[DnsAlertManager] = None


def get_alert_manager() -> DnsAlertManager:
    """Get or create the singleton alert manager."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = DnsAlertManager()
    return _alert_manager
