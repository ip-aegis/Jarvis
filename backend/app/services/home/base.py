"""Base home automation service with abstract interface."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)


class DeviceCapability(str, Enum):
    """Standardized device capabilities."""

    # Ring/Camera
    MOTION_DETECT = "motion_detect"
    VIDEO_STREAM = "video_stream"
    TWO_WAY_AUDIO = "two_way_audio"
    SNAPSHOT = "snapshot"
    RING = "ring"
    BATTERY = "battery"

    # Thermostat
    TEMPERATURE_READ = "temperature_read"
    TEMPERATURE_SET = "temperature_set"
    HUMIDITY_READ = "humidity_read"
    MODE_CONTROL = "mode_control"

    # Appliances
    POWER_CONTROL = "power_control"
    CYCLE_CONTROL = "cycle_control"
    CYCLE_STATUS = "cycle_status"
    NOTIFICATIONS = "notifications"

    # Media
    PLAYBACK_CONTROL = "playback_control"
    VOLUME_CONTROL = "volume_control"
    AIRPLAY = "airplay"
    NOW_PLAYING = "now_playing"


@dataclass
class DeviceState:
    """Standardized device state representation."""

    device_id: str
    platform: str
    online: bool
    state: dict[str, Any]
    last_updated: datetime
    capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "platform": self.platform,
            "online": self.online,
            "state": self.state,
            "last_updated": self.last_updated.isoformat(),
            "capabilities": self.capabilities,
        }


@dataclass
class DeviceEvent:
    """Standardized event from device."""

    device_id: str
    event_type: str
    title: str
    message: str
    data: dict[str, Any]
    occurred_at: datetime
    severity: str = "info"  # info, warning, alert, critical
    media_url: Optional[str] = None
    thumbnail_url: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "event_type": self.event_type,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "occurred_at": self.occurred_at.isoformat(),
            "severity": self.severity,
            "media_url": self.media_url,
            "thumbnail_url": self.thumbnail_url,
        }


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    pass


class DeviceConnectionError(Exception):
    """Raised when device connection fails."""

    pass


class DeviceNotFoundError(Exception):
    """Raised when device is not found."""

    pass


class ActionNotSupportedError(Exception):
    """Raised when action is not supported by device."""

    pass


class BaseHomeService(ABC):
    """Abstract base class for home automation device services.

    Each platform (Ring, LG ThinQ, Bosch, etc.) implements this interface
    to provide a consistent API for device discovery, state management,
    and action execution.
    """

    platform: str = (
        ""  # Override in subclass: "ring", "lg_thinq", "bosch", "homekit", "apple_media"
    )

    def __init__(self, credentials: dict[str, Any]):
        """Initialize service with platform credentials.

        Args:
            credentials: Platform-specific authentication credentials.
                Could include: access_token, refresh_token, username, password,
                api_key, client_id, client_secret, etc.
        """
        self.credentials = credentials
        self._authenticated = False
        self._client = None
        self._logger = logger.bind(platform=self.platform)

    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the device API/platform.

        Returns:
            True if authentication successful, False otherwise.

        Raises:
            AuthenticationError: If authentication fails.
        """
        pass

    async def refresh_token(self) -> bool:
        """Refresh OAuth tokens if applicable.

        Default implementation does nothing - override for OAuth platforms.

        Returns:
            True if token refresh successful or not needed.
        """
        return True

    @abstractmethod
    async def discover_devices(self) -> list[dict[str, Any]]:
        """Discover all devices on this platform.

        Returns:
            List of device dicts with at minimum:
            {
                "device_id": str,
                "name": str,
                "device_type": str,
                "model": str (optional),
                "capabilities": List[str],
                "state": Dict[str, Any] (optional),
            }
        """
        pass

    @abstractmethod
    async def get_device_state(self, device_id: str) -> DeviceState:
        """Get current state of a specific device.

        Args:
            device_id: The platform-specific device identifier.

        Returns:
            DeviceState with current device information.

        Raises:
            DeviceNotFoundError: If device doesn't exist.
            DeviceConnectionError: If can't reach device.
        """
        pass

    @abstractmethod
    async def execute_action(
        self, device_id: str, action: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute an action on a device.

        Args:
            device_id: The platform-specific device identifier.
            action: Action name (e.g., "play", "pause", "set_temperature").
            params: Action parameters.

        Returns:
            Result dict with at minimum {"success": bool}.

        Raises:
            DeviceNotFoundError: If device doesn't exist.
            ActionNotSupportedError: If action not supported.
            DeviceConnectionError: If can't reach device.
        """
        pass

    async def get_recent_events(self, device_id: str, limit: int = 10) -> list[DeviceEvent]:
        """Get recent events from a device.

        Default implementation returns empty list - override for devices
        that support event history (like Ring).

        Args:
            device_id: The platform-specific device identifier.
            limit: Maximum number of events to return.

        Returns:
            List of DeviceEvent objects.
        """
        return []

    async def subscribe_events(self, device_id: str) -> AsyncGenerator[DeviceEvent, None]:
        """Subscribe to real-time events from device.

        Default implementation raises NotImplementedError - override for
        devices that support real-time event streams.

        Args:
            device_id: The platform-specific device identifier.

        Yields:
            DeviceEvent objects as they occur.
        """
        raise NotImplementedError("Event subscription not supported for this platform")
        yield  # Make this a generator

    async def health_check(self) -> bool:
        """Check if service is connected and healthy.

        Returns:
            True if service is operational.
        """
        try:
            if not self._authenticated:
                return await self.authenticate()
            return True
        except Exception as e:
            self._logger.warning("health_check_failed", error=str(e))
            return False

    def get_supported_actions(self, device_type: str) -> list[str]:
        """Get list of actions supported for a device type.

        Override in subclass to provide device-specific actions.

        Args:
            device_type: Type of device (doorbell, washer, etc.)

        Returns:
            List of action names.
        """
        return []

    async def close(self) -> None:
        """Clean up resources and close connections.

        Override in subclass if cleanup is needed.
        """
        self._authenticated = False
        self._client = None


def with_retry(func):
    """Decorator to add retry logic with exponential backoff."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((DeviceConnectionError, ConnectionError)),
        before_sleep=lambda retry_state: logger.warning(
            "retry_attempt", attempt=retry_state.attempt_number, func=func.__name__
        ),
    )(func)
