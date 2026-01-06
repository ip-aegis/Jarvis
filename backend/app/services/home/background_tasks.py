"""Background tasks for home automation event polling and device monitoring."""

import asyncio
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import HomeDevice, HomeEvent, HomePlatformCredential

logger = structlog.get_logger(__name__)


def serialize_for_json(obj):
    """Recursively convert datetime objects to ISO strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    return obj


class HomeEventPoller:
    """Background task for polling device events.

    Periodically checks connected platforms for new events (Ring motion/rings,
    appliance cycle completions, etc.) and stores them in the database.
    """

    def __init__(self, poll_interval: int = 30):
        """Initialize event poller.

        Args:
            poll_interval: Seconds between polls (default: 30).
        """
        self._poll_interval = poll_interval
        self._running = False
        self._logger = logger.bind(component="event_poller")
        self._last_event_times: dict[str, datetime] = {}

    async def start(self):
        """Start the event polling loop."""
        if self._running:
            return

        self._running = True
        self._logger.info("event_poller_started", interval=self._poll_interval)
        asyncio.create_task(self._poll_loop())

    async def stop(self):
        """Stop the event polling loop."""
        self._running = False
        self._logger.info("event_poller_stopped")

    async def _poll_loop(self):
        """Main polling loop."""
        while self._running:
            try:
                await self._poll_all_platforms()
            except Exception as e:
                self._logger.error("poll_loop_error", error=str(e))

            await asyncio.sleep(self._poll_interval)

    async def _poll_all_platforms(self):
        """Poll all connected platforms for events."""
        from app.services.home import device_manager

        for platform in device_manager.connected_platforms:
            try:
                await self._poll_platform(platform)
            except Exception as e:
                self._logger.warning("platform_poll_failed", platform=platform, error=str(e))

    async def _poll_platform(self, platform: str):
        """Poll a specific platform for events."""
        from app.services.home import device_manager

        service = device_manager.get_service(platform)
        if not service:
            return

        db = SessionLocal()
        try:
            # Get devices for this platform
            devices = db.query(HomeDevice).filter_by(platform=platform, status="online").all()

            for device in devices:
                try:
                    # Get recent events
                    events = await service.get_recent_events(device.device_id, limit=10)

                    # Store new events
                    for event in events:
                        await self._store_event_if_new(event, device, db)

                    # Update device state
                    state = await service.get_device_state(device.device_id)
                    if state:
                        old_state = device.state or {}
                        device.state = state.state
                        device.last_seen = datetime.utcnow()
                        device.status = "online" if state.online else "offline"
                        db.commit()

                        # Check for state change triggers
                        if old_state != state.state:
                            await self._handle_state_change(device.id, old_state, state.state)

                except Exception as e:
                    self._logger.warning("device_poll_failed", device_id=device.id, error=str(e))

        finally:
            db.close()

    async def _store_event_if_new(self, event: Any, device: HomeDevice, db: Session):
        """Store event if it's new (not already in database)."""
        # Check if event already exists
        if hasattr(event, "occurred_at") and event.occurred_at:
            existing = (
                db.query(HomeEvent)
                .filter(
                    HomeEvent.device_id == device.id,
                    HomeEvent.event_type == event.event_type,
                    HomeEvent.occurred_at == event.occurred_at,
                )
                .first()
            )

            if existing:
                return

        # Create new event - serialize data to handle datetime objects
        event_data = getattr(event, "data", {})
        if event_data:
            event_data = serialize_for_json(event_data)

        db_event = HomeEvent(
            device_id=device.id,
            event_type=event.event_type,
            severity=getattr(event, "severity", "info"),
            title=event.title,
            message=getattr(event, "message", ""),
            data=event_data,
            media_url=getattr(event, "media_url", None),
            occurred_at=getattr(event, "occurred_at", datetime.utcnow()),
        )
        db.add(db_event)
        db.commit()

        self._logger.info("event_stored", device_id=device.id, event_type=event.event_type)

        # Trigger automation engine
        from app.services.home import automation_engine

        await automation_engine.handle_event(db_event)

    async def _handle_state_change(
        self, device_id: int, old_state: dict[str, Any], new_state: dict[str, Any]
    ):
        """Handle device state change for automations."""
        from app.services.home import automation_engine

        await automation_engine.handle_state_change(device_id, old_state, new_state)


class DeviceStateRefresher:
    """Background task for refreshing device states.

    Periodically updates device states from platforms to keep
    the database in sync with actual device states.
    """

    def __init__(self, refresh_interval: int = 60):
        """Initialize state refresher.

        Args:
            refresh_interval: Seconds between refreshes (default: 60).
        """
        self._refresh_interval = refresh_interval
        self._running = False
        self._logger = logger.bind(component="state_refresher")

    async def start(self):
        """Start the state refresh loop."""
        if self._running:
            return

        self._running = True
        self._logger.info("state_refresher_started", interval=self._refresh_interval)
        asyncio.create_task(self._refresh_loop())

    async def stop(self):
        """Stop the state refresh loop."""
        self._running = False
        self._logger.info("state_refresher_stopped")

    async def _refresh_loop(self):
        """Main refresh loop."""
        while self._running:
            try:
                await self._refresh_all_states()
            except Exception as e:
                self._logger.error("refresh_loop_error", error=str(e))

            await asyncio.sleep(self._refresh_interval)

    async def _refresh_all_states(self):
        """Refresh states for all devices."""
        from app.services.home import device_manager

        db = SessionLocal()
        try:
            # Get all devices
            devices = db.query(HomeDevice).all()

            for device in devices:
                if device.platform not in device_manager.connected_platforms:
                    continue

                try:
                    state = await device_manager.get_device_state(device.platform, device.device_id)

                    if state:
                        device.state = state.state
                        device.status = "online" if state.online else "offline"
                        device.last_seen = datetime.utcnow()

                except Exception as e:
                    self._logger.warning("state_refresh_failed", device_id=device.id, error=str(e))
                    # Mark as offline if refresh fails
                    if device.last_seen:
                        stale_time = datetime.utcnow() - timedelta(minutes=5)
                        if device.last_seen < stale_time:
                            device.status = "offline"

            db.commit()

        finally:
            db.close()


class PlatformHealthChecker:
    """Background task for checking platform connectivity."""

    def __init__(self, check_interval: int = 300):
        """Initialize health checker.

        Args:
            check_interval: Seconds between checks (default: 300 = 5 min).
        """
        self._check_interval = check_interval
        self._running = False
        self._logger = logger.bind(component="health_checker")

    async def start(self):
        """Start the health check loop."""
        if self._running:
            return

        self._running = True
        self._logger.info("health_checker_started", interval=self._check_interval)
        asyncio.create_task(self._check_loop())

    async def stop(self):
        """Stop the health check loop."""
        self._running = False
        self._logger.info("health_checker_stopped")

    async def _check_loop(self):
        """Main health check loop."""
        while self._running:
            try:
                await self._check_all_platforms()
            except Exception as e:
                self._logger.error("health_check_error", error=str(e))

            await asyncio.sleep(self._check_interval)

    async def _check_all_platforms(self):
        """Check health of all connected platforms."""
        from app.services.home import device_manager

        health = await device_manager.health_check_all()

        for platform, is_healthy in health.items():
            if not is_healthy:
                self._logger.warning("platform_unhealthy", platform=platform)

                # Try to reconnect
                try:
                    await self._reconnect_platform(platform)
                except Exception as e:
                    self._logger.error("reconnect_failed", platform=platform, error=str(e))

    async def _reconnect_platform(self, platform: str):
        """Attempt to reconnect a platform."""
        from app.services.home import device_manager

        db = SessionLocal()
        try:
            # Get stored credentials
            creds = db.query(HomePlatformCredential).filter_by(platform=platform).first()

            if creds:
                credentials = creds.credentials or {}
                await device_manager.disconnect_service(platform)
                await device_manager.initialize_service(platform, credentials)
                self._logger.info("platform_reconnected", platform=platform)

        finally:
            db.close()


# Global instances
event_poller = HomeEventPoller()
state_refresher = DeviceStateRefresher()
health_checker = PlatformHealthChecker()


async def reconnect_stored_platforms():
    """Reconnect to platforms with stored credentials on startup."""
    from app.services.home import device_manager

    db = SessionLocal()
    try:
        # Get all stored credentials
        creds_list = db.query(HomePlatformCredential).all()

        for creds in creds_list:
            try:
                platform = creds.platform

                # Build credentials dict from model fields
                credentials = {}

                # First, check for full token dict in auth_data (preferred for Ring)
                if creds.auth_data and isinstance(creds.auth_data, dict):
                    # auth_data may contain {"token": {...}} for Ring
                    if "token" in creds.auth_data:
                        credentials["token"] = creds.auth_data["token"]
                    else:
                        credentials.update(creds.auth_data)

                # Add OAuth tokens (backup if not in auth_data)
                if creds.refresh_token and "token" not in credentials:
                    credentials["refresh_token"] = creds.refresh_token
                if creds.access_token:
                    credentials["access_token"] = creds.access_token

                # Add API keys
                if creds.api_key:
                    credentials["api_key"] = creds.api_key
                if creds.client_id:
                    credentials["client_id"] = creds.client_id
                if creds.client_secret:
                    credentials["client_secret"] = creds.client_secret

                # Skip if no credentials or already connected
                if not credentials:
                    logger.debug("no_credentials_for_platform", platform=platform)
                    continue

                if platform in device_manager.connected_platforms:
                    continue

                logger.info("reconnecting_platform", platform=platform)
                await device_manager.initialize_service(platform, credentials)
                logger.info("platform_reconnected", platform=platform)

            except Exception as e:
                logger.warning("platform_reconnect_failed", platform=creds.platform, error=str(e))
    finally:
        db.close()


async def start_background_tasks():
    """Start all home automation background tasks."""
    from app.services.home import automation_engine

    # First, reconnect to platforms with stored credentials
    await reconnect_stored_platforms()

    await event_poller.start()
    await state_refresher.start()
    await health_checker.start()
    await automation_engine.start()

    logger.info("home_background_tasks_started")


async def stop_background_tasks():
    """Stop all home automation background tasks."""
    from app.services.home import automation_engine

    await event_poller.stop()
    await state_refresher.stop()
    await health_checker.stop()
    await automation_engine.stop()

    logger.info("home_background_tasks_stopped")
