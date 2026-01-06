"""Bosch Home Connect appliance service implementation."""

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


class BoschHomeConnectService(BaseHomeService):
    """Service for Bosch/Siemens Home Connect appliances.

    Uses the Home Connect API for dishwashers, ovens, washers, etc.
    Requires OAuth authentication through developer.home-connect.com
    """

    platform = "bosch"

    # Device type mapping
    DEVICE_TYPE_MAP = {
        "Dishwasher": "dishwasher",
        "Washer": "washer",
        "Dryer": "dryer",
        "WasherDryer": "washer",
        "Oven": "oven",
        "CoffeeMaker": "coffee_maker",
        "FridgeFreezer": "refrigerator",
        "Refrigerator": "refrigerator",
        "Freezer": "freezer",
    }

    def __init__(self, credentials: dict[str, Any]):
        """Initialize Bosch Home Connect service.

        Args:
            credentials: Dict containing:
                - client_id: OAuth client ID from developer portal
                - client_secret: OAuth client secret
                - access_token: OAuth access token
                - refresh_token: OAuth refresh token
                - redirect_uri: OAuth redirect URI
        """
        super().__init__(credentials)
        self._client = None
        self._appliances_cache: dict[str, Any] = {}

    async def authenticate(self) -> bool:
        """Authenticate with Home Connect API."""
        try:
            # Import here to handle missing dependency
            from homeconnect.api import HomeConnectAPI

            def _auth():
                client_id = self.credentials.get("client_id")
                client_secret = self.credentials.get("client_secret")
                redirect_uri = self.credentials.get("redirect_uri", "https://localhost/callback")

                if not client_id:
                    raise AuthenticationError(
                        "Bosch Home Connect requires client_id from developer portal"
                    )

                self._client = HomeConnectAPI(
                    client_id=client_id,
                    client_secret=client_secret,
                    redirect_uri=redirect_uri,
                )

                # Set existing token
                access_token = self.credentials.get("access_token")
                refresh_token = self.credentials.get("refresh_token")

                if access_token and refresh_token:
                    self._client.set_token(
                        {
                            "access_token": access_token,
                            "refresh_token": refresh_token,
                            "token_type": "Bearer",
                        }
                    )
                else:
                    raise AuthenticationError(
                        "Bosch Home Connect requires access_token and refresh_token. "
                        "Complete OAuth flow through developer.home-connect.com first."
                    )

                # Test connection
                self._client.get_appliances()
                return True

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, _auth)
            self._authenticated = result
            return result

        except ImportError:
            raise AuthenticationError("homeconnect not installed. Run: pip install homeconnect")
        except Exception as e:
            self._logger.error("bosch_auth_failed", error=str(e))
            raise AuthenticationError(f"Bosch Home Connect auth failed: {e}")

    async def refresh_token(self) -> bool:
        """Refresh Home Connect OAuth tokens."""
        if not self._client:
            return False

        def _refresh():
            try:
                self._client.refresh_token()
                return True
            except Exception as e:
                self._logger.error("bosch_refresh_failed", error=str(e))
                return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _refresh)

    async def discover_devices(self) -> list[dict[str, Any]]:
        """Discover all Home Connect appliances."""
        if not self._client:
            raise DeviceConnectionError("Home Connect not authenticated")

        def _discover():
            devices = []
            appliances = self._client.get_appliances()

            for appliance in appliances:
                device_type = self.DEVICE_TYPE_MAP.get(appliance.type, appliance.type.lower())

                # Cache appliance reference
                self._appliances_cache[appliance.haId] = appliance

                # Get capabilities
                capabilities = self._get_capabilities(appliance.type)

                # Get current status
                state = {}
                try:
                    status = appliance.get_status()
                    settings = appliance.get_settings()
                    state = self._parse_status(appliance.type, status, settings)
                except Exception as e:
                    self._logger.warning(
                        "bosch_status_failed", device_id=appliance.haId, error=str(e)
                    )

                devices.append(
                    {
                        "device_id": appliance.haId,
                        "name": appliance.name,
                        "device_type": device_type,
                        "model": f"{appliance.brand} {appliance.vib}",
                        "capabilities": capabilities,
                        "state": state,
                    }
                )

            return devices

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _discover)

    async def get_device_state(self, device_id: str) -> DeviceState:
        """Get current state of a Home Connect appliance."""
        if not self._client:
            raise DeviceConnectionError("Home Connect not authenticated")

        def _get_state():
            appliance = self._appliances_cache.get(device_id)

            if not appliance:
                # Refresh appliances list
                appliances = self._client.get_appliances()
                for a in appliances:
                    if a.haId == device_id:
                        appliance = a
                        self._appliances_cache[device_id] = a
                        break

            if not appliance:
                raise DeviceNotFoundError(f"Appliance {device_id} not found")

            device_type = self.DEVICE_TYPE_MAP.get(appliance.type, appliance.type.lower())

            try:
                status = appliance.get_status()
                settings = appliance.get_settings()
                state = self._parse_status(appliance.type, status, settings)
                online = appliance.connected
            except Exception as e:
                self._logger.warning("bosch_state_failed", device_id=device_id, error=str(e))
                state = {}
                online = False

            return DeviceState(
                device_id=device_id,
                platform="bosch",
                online=online,
                state=state,
                last_updated=datetime.utcnow(),
                capabilities=self._get_capabilities(appliance.type),
            )

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_state)

    async def execute_action(
        self, device_id: str, action: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute action on Home Connect appliance.

        Supported actions:
        - start_program: Start a program (program: str, options: dict)
        - stop_program: Stop current program
        - pause_program: Pause current program
        - resume_program: Resume paused program

        Args:
            device_id: Home Connect appliance ID.
            action: Action name.
            params: Action parameters.

        Returns:
            Result dict.
        """
        if not self._client:
            return {"success": False, "error": "Home Connect not authenticated"}

        def _execute():
            appliance = self._appliances_cache.get(device_id)

            if not appliance:
                appliances = self._client.get_appliances()
                for a in appliances:
                    if a.haId == device_id:
                        appliance = a
                        self._appliances_cache[device_id] = a
                        break

            if not appliance:
                return {"success": False, "error": f"Appliance {device_id} not found"}

            try:
                if action == "start_program":
                    program = params.get("program")
                    options = params.get("options", {})

                    if not program:
                        # Use default program based on appliance type
                        if appliance.type == "Dishwasher":
                            program = "Dishcare.Dishwasher.Program.Auto2"
                        elif appliance.type == "Washer":
                            program = "LaundryCare.Washer.Program.Cotton"
                        else:
                            return {"success": False, "error": "Program required"}

                    appliance.start_program(program_key=program, options=options)
                    return {"success": True, "action": "start_program", "program": program}

                elif action == "stop_program":
                    appliance.stop_program()
                    return {"success": True, "action": "stop_program"}

                elif action == "pause_program":
                    appliance.pause_program()
                    return {"success": True, "action": "pause_program"}

                elif action == "resume_program":
                    appliance.resume_program()
                    return {"success": True, "action": "resume_program"}

                elif action == "set_setting":
                    key = params.get("key")
                    value = params.get("value")
                    if key and value is not None:
                        appliance.set_setting(key, value)
                        return {"success": True, "setting": key, "value": value}
                    return {"success": False, "error": "key and value required"}

                else:
                    return {"success": False, "error": f"Unknown action: {action}"}

            except Exception as e:
                return {"success": False, "error": str(e)}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _execute)

    def _get_capabilities(self, bosch_type: str) -> list[str]:
        """Get capabilities for appliance type."""
        base = [
            DeviceCapability.POWER_CONTROL.value,
            DeviceCapability.NOTIFICATIONS.value,
        ]

        if bosch_type in ("Dishwasher", "Washer", "Dryer", "WasherDryer"):
            return base + [
                DeviceCapability.CYCLE_CONTROL.value,
                DeviceCapability.CYCLE_STATUS.value,
            ]
        elif bosch_type in ("Oven", "CoffeeMaker"):
            return base + [
                DeviceCapability.CYCLE_CONTROL.value,
                DeviceCapability.TEMPERATURE_READ.value,
            ]
        elif bosch_type in ("FridgeFreezer", "Refrigerator", "Freezer"):
            return base + [
                DeviceCapability.TEMPERATURE_READ.value,
                DeviceCapability.TEMPERATURE_SET.value,
            ]

        return base

    def _parse_status(self, bosch_type: str, status: dict, settings: dict) -> dict[str, Any]:
        """Parse Home Connect status into standard format."""
        result = {
            "power": self._get_value(status, "BSH.Common.Status.OperationState") != "Inactive",
            "remote_control": self._get_value(
                settings, "BSH.Common.Setting.RemoteControlActive", False
            ),
            "remote_start": self._get_value(
                settings, "BSH.Common.Setting.RemoteControlStartAllowed", False
            ),
        }

        # Operation state
        op_state = self._get_value(status, "BSH.Common.Status.OperationState")
        if op_state:
            result["operation_state"] = op_state.split(".")[-1] if "." in op_state else op_state

        # Door state
        door_state = self._get_value(status, "BSH.Common.Status.DoorState")
        if door_state:
            result["door_open"] = door_state == "Open"

        # Active program
        active_program = self._get_value(status, "BSH.Common.Root.ActiveProgram")
        if active_program:
            result["active_program"] = active_program.split(".")[-1]

        # Remaining time
        remaining = self._get_value(status, "BSH.Common.Option.RemainingProgramTime")
        if remaining is not None:
            result["remaining_time"] = self._format_time(remaining)

        # Progress
        progress = self._get_value(status, "BSH.Common.Option.ProgramProgress")
        if progress is not None:
            result["progress"] = progress

        # Elapsed time
        elapsed = self._get_value(status, "BSH.Common.Option.ElapsedProgramTime")
        if elapsed is not None:
            result["elapsed_time"] = self._format_time(elapsed)

        return result

    def _get_value(self, data: dict, key: str, default: Any = None) -> Any:
        """Get value from nested status dict."""
        if not data:
            return default
        item = data.get(key, {})
        if isinstance(item, dict):
            return item.get("value", default)
        return item if item is not None else default

    def _format_time(self, seconds: Optional[int]) -> Optional[str]:
        """Format seconds into HH:MM string."""
        if seconds is None:
            return None
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def get_supported_actions(self, device_type: str) -> list[str]:
        """Get supported actions for device type."""
        if device_type in ("dishwasher", "washer", "dryer"):
            return ["start_program", "stop_program", "pause_program", "resume_program"]
        elif device_type in ("oven", "coffee_maker"):
            return ["start_program", "stop_program"]
        return []

    async def close(self) -> None:
        """Clean up Home Connect connection."""
        self._client = None
        self._appliances_cache.clear()
        self._authenticated = False
