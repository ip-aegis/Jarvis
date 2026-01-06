"""LG ThinQ smart appliance service implementation."""

import asyncio
from datetime import datetime
from typing import Any, Optional

import structlog

from .base import (
    AuthenticationError,
    BaseHomeService,
    DeviceCapability,
    DeviceConnectionError,
    DeviceNotFoundError,
    DeviceState,
)

logger = structlog.get_logger(__name__)


class LGThinQService(BaseHomeService):
    """Service for LG ThinQ smart appliances.

    Uses the official pythinqconnect library for API access.
    Supports washers, dryers, refrigerators, dishwashers, and more.
    """

    platform = "lg_thinq"

    # Device type mapping from LG to our types
    DEVICE_TYPE_MAP = {
        "WASHER": "washer",
        "DRYER": "dryer",
        "WASHER_DRYER": "washer",  # Combo units
        "DISHWASHER": "dishwasher",
        "REFRIGERATOR": "refrigerator",
        "AIR_CONDITIONER": "air_conditioner",
        "AIR_PURIFIER": "air_purifier",
        "OVEN": "oven",
        "RANGE": "oven",
        "MICROWAVE": "microwave",
    }

    def __init__(self, credentials: dict[str, Any]):
        """Initialize LG ThinQ service.

        Args:
            credentials: Dict containing:
                - access_token: OAuth access token
                - refresh_token: OAuth refresh token
                - country_code: Country code (default: US)
                - language_code: Language code (default: en-US)
        """
        super().__init__(credentials)
        self._api = None
        self._devices_cache: dict[str, Any] = {}

    async def authenticate(self) -> bool:
        """Authenticate with LG ThinQ API.

        Returns:
            True if authentication successful.
        """
        try:
            # Import here to handle missing dependency gracefully
            from thinqconnect import ThinQApi

            def _auth():
                self._api = ThinQApi(
                    country_code=self.credentials.get("country_code", "US"),
                    language_code=self.credentials.get("language_code", "en-US"),
                )

                # Set tokens if available
                access_token = self.credentials.get("access_token")
                refresh_token = self.credentials.get("refresh_token")

                if access_token and refresh_token:
                    self._api.set_token(access_token, refresh_token)
                else:
                    raise AuthenticationError(
                        "LG ThinQ requires access_token and refresh_token. "
                        "Use the LG ThinQ app to get initial tokens."
                    )

                # Test connection by fetching devices
                self._api.get_devices()
                return True

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, _auth)
            self._authenticated = result
            return result

        except ImportError:
            raise AuthenticationError(
                "pythinqconnect not installed. Run: pip install pythinqconnect"
            )
        except Exception as e:
            self._logger.error("lg_thinq_auth_failed", error=str(e))
            raise AuthenticationError(f"LG ThinQ authentication failed: {e}")

    async def refresh_token(self) -> bool:
        """Refresh LG ThinQ OAuth tokens."""
        if not self._api:
            return False

        def _refresh():
            try:
                self._api.refresh_token()
                return True
            except Exception as e:
                self._logger.error("lg_token_refresh_failed", error=str(e))
                return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _refresh)

    async def discover_devices(self) -> list[dict[str, Any]]:
        """Discover all LG ThinQ devices."""
        if not self._api:
            raise DeviceConnectionError("LG ThinQ not authenticated")

        def _discover():
            devices = []
            lg_devices = self._api.get_devices()

            for device in lg_devices:
                device_type = self.DEVICE_TYPE_MAP.get(
                    device.device_type, device.device_type.lower()
                )

                # Cache device reference
                self._devices_cache[device.device_id] = device

                # Get capabilities based on device type
                capabilities = self._get_capabilities(device.device_type)

                # Get current status
                state = {}
                try:
                    status = device.get_status()
                    state = self._parse_status(device.device_type, status)
                except Exception as e:
                    self._logger.warning(
                        "lg_status_fetch_failed", device_id=device.device_id, error=str(e)
                    )

                devices.append(
                    {
                        "device_id": device.device_id,
                        "name": device.alias or device.device_id,
                        "device_type": device_type,
                        "model": getattr(device, "model_name", None),
                        "firmware": getattr(device, "firmware_version", None),
                        "capabilities": capabilities,
                        "state": state,
                    }
                )

            return devices

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _discover)

    async def get_device_state(self, device_id: str) -> DeviceState:
        """Get current state of an LG device."""
        if not self._api:
            raise DeviceConnectionError("LG ThinQ not authenticated")

        def _get_state():
            # Refresh device list
            lg_devices = self._api.get_devices()

            for device in lg_devices:
                if device.device_id == device_id:
                    self._devices_cache[device_id] = device

                    device_type = self.DEVICE_TYPE_MAP.get(
                        device.device_type, device.device_type.lower()
                    )

                    try:
                        status = device.get_status()
                        state = self._parse_status(device.device_type, status)
                        online = status.get("online", True)
                    except Exception as e:
                        self._logger.warning("lg_status_failed", device_id=device_id, error=str(e))
                        state = {}
                        online = False

                    return DeviceState(
                        device_id=device_id,
                        platform="lg_thinq",
                        online=online,
                        state=state,
                        last_updated=datetime.utcnow(),
                        capabilities=self._get_capabilities(device.device_type),
                    )

            raise DeviceNotFoundError(f"LG device {device_id} not found")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_state)

    async def execute_action(
        self, device_id: str, action: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute action on LG device.

        Supported actions:
        - power_on: Turn on device
        - power_off: Turn off device
        - start_cycle: Start wash/dry cycle (course: str)
        - pause: Pause current cycle
        - resume: Resume paused cycle

        Args:
            device_id: LG device ID.
            action: Action name.
            params: Action parameters.

        Returns:
            Result dict.
        """
        if not self._api:
            return {"success": False, "error": "LG ThinQ not authenticated"}

        def _execute():
            device = self._devices_cache.get(device_id)

            if not device:
                # Try to find device
                lg_devices = self._api.get_devices()
                for d in lg_devices:
                    if d.device_id == device_id:
                        device = d
                        self._devices_cache[device_id] = device
                        break

            if not device:
                return {"success": False, "error": f"Device {device_id} not found"}

            try:
                if action == "power_on":
                    device.power_on()
                    return {"success": True, "action": "power_on"}

                elif action == "power_off":
                    device.power_off()
                    return {"success": True, "action": "power_off"}

                elif action == "start_cycle":
                    course = params.get("course", "normal")
                    device.start(course=course)
                    return {"success": True, "action": "start_cycle", "course": course}

                elif action == "pause":
                    device.pause()
                    return {"success": True, "action": "pause"}

                elif action == "resume":
                    device.resume()
                    return {"success": True, "action": "resume"}

                elif action == "set_temperature":
                    # For AC/refrigerator
                    temp = params.get("temperature")
                    if temp is not None:
                        device.set_temperature(temp)
                        return {"success": True, "temperature": temp}
                    return {"success": False, "error": "Temperature required"}

                else:
                    return {"success": False, "error": f"Unknown action: {action}"}

            except Exception as e:
                return {"success": False, "error": str(e)}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _execute)

    def _get_capabilities(self, lg_device_type: str) -> list[str]:
        """Get capabilities for device type."""
        base = [
            DeviceCapability.POWER_CONTROL.value,
            DeviceCapability.NOTIFICATIONS.value,
        ]

        if lg_device_type in ("WASHER", "DRYER", "WASHER_DRYER"):
            return base + [
                DeviceCapability.CYCLE_CONTROL.value,
                DeviceCapability.CYCLE_STATUS.value,
            ]
        elif lg_device_type == "DISHWASHER":
            return base + [
                DeviceCapability.CYCLE_CONTROL.value,
                DeviceCapability.CYCLE_STATUS.value,
            ]
        elif lg_device_type == "AIR_CONDITIONER":
            return base + [
                DeviceCapability.TEMPERATURE_READ.value,
                DeviceCapability.TEMPERATURE_SET.value,
                DeviceCapability.MODE_CONTROL.value,
            ]
        elif lg_device_type == "REFRIGERATOR":
            return base + [
                DeviceCapability.TEMPERATURE_READ.value,
                DeviceCapability.TEMPERATURE_SET.value,
            ]

        return base

    def _parse_status(self, lg_device_type: str, status: dict) -> dict[str, Any]:
        """Parse LG device status into standard format."""
        result = {
            "power": status.get("state") == "POWER_ON",
            "online": status.get("online", True),
        }

        if lg_device_type in ("WASHER", "DRYER", "WASHER_DRYER"):
            result.update(
                {
                    "cycle_state": status.get("current_course") or status.get("state"),
                    "remaining_time": self._format_time(status.get("remain_time")),
                    "initial_time": self._format_time(status.get("initial_time")),
                    "door_locked": status.get("door_lock") == "LOCK",
                    "error": status.get("error_message"),
                }
            )

            if lg_device_type in ("WASHER", "WASHER_DRYER"):
                result.update(
                    {
                        "wash_temperature": status.get("temp"),
                        "spin_speed": status.get("spin"),
                        "rinse_option": status.get("rinse"),
                    }
                )

        elif lg_device_type == "DISHWASHER":
            result.update(
                {
                    "cycle_state": status.get("current_course") or status.get("state"),
                    "remaining_time": self._format_time(status.get("remain_time")),
                    "door_open": status.get("door_state") == "OPEN",
                    "error": status.get("error_message"),
                }
            )

        elif lg_device_type == "AIR_CONDITIONER":
            result.update(
                {
                    "current_temperature": status.get("current_temp"),
                    "target_temperature": status.get("target_temp"),
                    "mode": status.get("operation_mode"),
                    "fan_speed": status.get("fan_speed"),
                }
            )

        elif lg_device_type == "REFRIGERATOR":
            result.update(
                {
                    "fridge_temp": status.get("fridge_temp"),
                    "freezer_temp": status.get("freezer_temp"),
                    "door_open": status.get("door_state") == "OPEN",
                    "ice_plus": status.get("ice_plus"),
                }
            )

        return result

    def _format_time(self, minutes: Optional[int]) -> Optional[str]:
        """Format minutes into HH:MM string."""
        if minutes is None:
            return None
        hours = minutes // 60
        mins = minutes % 60
        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"

    def get_supported_actions(self, device_type: str) -> list[str]:
        """Get supported actions for device type."""
        if device_type in ("washer", "dryer"):
            return ["power_on", "power_off", "start_cycle", "pause", "resume"]
        elif device_type == "dishwasher":
            return ["power_on", "power_off", "start_cycle", "pause"]
        elif device_type in ("air_conditioner", "refrigerator"):
            return ["power_on", "power_off", "set_temperature"]
        return ["power_on", "power_off"]

    async def close(self) -> None:
        """Clean up LG ThinQ connection."""
        self._api = None
        self._devices_cache.clear()
        self._authenticated = False
