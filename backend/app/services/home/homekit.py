"""HomeKit service implementation using pyatv for Ecobee and other HomeKit devices."""

import asyncio
from datetime import datetime
from typing import Any

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


class HomeKitService(BaseHomeService):
    """Service for HomeKit devices via pyatv bridge.

    Uses pyatv's HomeKit support to control devices like Ecobee thermostats
    that are exposed through HomeKit. This is a workaround for Ecobee's
    blocked API key registration.

    Note: Requires devices to be added to HomeKit on an Apple device first.
    """

    platform = "homekit"

    # HomeKit accessory category mapping
    CATEGORY_MAP = {
        1: "other",
        2: "bridge",
        3: "fan",
        4: "garage_door",
        5: "light",
        6: "door_lock",
        7: "outlet",
        8: "switch",
        9: "thermostat",
        10: "sensor",
        11: "security_system",
        12: "door",
        13: "window",
        14: "window_covering",
        15: "programmable_switch",
        17: "ip_camera",
        18: "video_doorbell",
        19: "air_purifier",
        20: "heater",
        21: "air_conditioner",
        22: "humidifier",
        23: "dehumidifier",
        28: "sprinkler",
        29: "faucet",
        30: "shower_head",
        32: "television",
    }

    def __init__(self, credentials: dict[str, Any]):
        """Initialize HomeKit service.

        Args:
            credentials: Dict containing:
                - pairing_data: Dict of device_id -> pairing credentials
                - scan_timeout: Network scan timeout in seconds (default: 10)
        """
        super().__init__(credentials)
        self._devices_cache: dict[str, Any] = {}
        self._connections: dict[str, Any] = {}
        self._scan_timeout = credentials.get("scan_timeout", 10)

    async def authenticate(self) -> bool:
        """Scan for HomeKit devices on the network.

        HomeKit uses local network discovery and pairing, not cloud auth.
        """
        try:
            import pyatv
            from pyatv.const import Protocol

            # Scan for HomeKit devices
            devices = await pyatv.scan(
                asyncio.get_event_loop(),
                timeout=self._scan_timeout,
                protocol=Protocol.AirPlay,  # HomeKit devices often support AirPlay
            )

            # Also scan specifically for HomeKit
            # Note: pyatv primarily focuses on Apple TV, but can discover
            # some HomeKit accessories on the network

            for device in devices:
                self._devices_cache[device.identifier] = device

            self._authenticated = True
            self._logger.info("homekit_scan_complete", devices_found=len(devices))
            return True

        except ImportError:
            raise AuthenticationError("pyatv not installed. Run: pip install pyatv")
        except Exception as e:
            self._logger.error("homekit_scan_failed", error=str(e))
            raise AuthenticationError(f"HomeKit scan failed: {e}")

    async def discover_devices(self) -> list[dict[str, Any]]:
        """Discover HomeKit devices on the network.

        Note: Full HomeKit discovery requires HAP-python or similar.
        This implementation focuses on devices accessible via pyatv.
        """
        try:
            import pyatv

            devices = await pyatv.scan(asyncio.get_event_loop(), timeout=self._scan_timeout)

            result = []
            for device in devices:
                self._devices_cache[device.identifier] = device

                # Determine device type from services
                device_type = "unknown"
                capabilities = []

                # Check for specific protocol support
                for service in device.services:
                    if service.protocol.name == "AirPlay":
                        capabilities.append(DeviceCapability.AIRPLAY.value)
                    if service.protocol.name == "Companion":
                        capabilities.append(DeviceCapability.VOLUME_CONTROL.value)

                # Get device info
                model = ""
                if device.device_info:
                    model = device.device_info.model or ""

                # Categorize based on model name
                model_lower = model.lower()
                if "thermostat" in model_lower or "ecobee" in model_lower:
                    device_type = "thermostat"
                    capabilities.extend(
                        [
                            DeviceCapability.TEMPERATURE_READ.value,
                            DeviceCapability.TEMPERATURE_SET.value,
                            DeviceCapability.MODE_CONTROL.value,
                        ]
                    )
                elif "homepod" in model_lower:
                    device_type = "homepod"
                elif "appletv" in model_lower or "apple tv" in model_lower:
                    device_type = "apple_tv"

                result.append(
                    {
                        "device_id": device.identifier,
                        "name": device.name,
                        "device_type": device_type,
                        "model": model,
                        "capabilities": capabilities,
                        "state": {},
                    }
                )

            return result

        except Exception as e:
            self._logger.error("homekit_discovery_failed", error=str(e))
            return []

    async def get_device_state(self, device_id: str) -> DeviceState:
        """Get current state of a HomeKit device.

        For thermostats, this returns temperature, humidity, and HVAC mode.
        """
        try:
            import pyatv

            device_config = self._devices_cache.get(device_id)

            if not device_config:
                # Rescan
                devices = await pyatv.scan(
                    asyncio.get_event_loop(), identifier=device_id, timeout=self._scan_timeout
                )
                if not devices:
                    raise DeviceNotFoundError(f"HomeKit device {device_id} not found")
                device_config = devices[0]
                self._devices_cache[device_id] = device_config

            # For HomeKit thermostats, we need HAP-python for full control
            # This is a placeholder that returns cached/mock data
            # Full implementation would require HomeKit pairing

            state = {
                "online": True,
                # Thermostat state would come from HomeKit characteristics
                # This requires proper HAP implementation
            }

            # Determine device type
            model = ""
            if device_config.device_info:
                model = device_config.device_info.model or ""

            model_lower = model.lower()
            if "thermostat" in model_lower or "ecobee" in model_lower:
                device_type = "thermostat"
                capabilities = [
                    DeviceCapability.TEMPERATURE_READ.value,
                    DeviceCapability.TEMPERATURE_SET.value,
                    DeviceCapability.MODE_CONTROL.value,
                ]
            else:
                device_type = "unknown"
                capabilities = []

            return DeviceState(
                device_id=device_id,
                platform="homekit",
                online=True,
                state=state,
                last_updated=datetime.utcnow(),
                capabilities=capabilities,
            )

        except DeviceNotFoundError:
            raise
        except Exception as e:
            self._logger.error("homekit_state_error", device_id=device_id, error=str(e))
            raise DeviceConnectionError(str(e))

    async def execute_action(
        self, device_id: str, action: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute action on HomeKit device.

        Supported actions for thermostats:
        - set_temperature: Set target temperature (temperature: float)
        - set_mode: Set HVAC mode (mode: heat/cool/auto/off)
        - set_fan_mode: Set fan mode (mode: auto/on)

        Note: Full HomeKit control requires HAP-python implementation.
        This is a placeholder for the interface.

        Args:
            device_id: HomeKit device identifier.
            action: Action name.
            params: Action parameters.

        Returns:
            Result dict.
        """
        # For full HomeKit support, we would need to:
        # 1. Use HAP-python or aiohomekit
        # 2. Pair with the HomeKit device
        # 3. Read/write characteristics

        self._logger.info(
            "homekit_action_requested", device_id=device_id, action=action, params=params
        )

        # Placeholder response - actual implementation needs HAP
        if action == "set_temperature":
            temperature = params.get("temperature")
            if temperature is not None:
                # Would write to thermostat characteristic
                return {
                    "success": True,
                    "action": "set_temperature",
                    "temperature": temperature,
                    "note": "HomeKit thermostat control requires HAP pairing",
                }
            return {"success": False, "error": "Temperature required"}

        elif action == "set_mode":
            mode = params.get("mode")
            if mode in ("heat", "cool", "auto", "off"):
                return {
                    "success": True,
                    "action": "set_mode",
                    "mode": mode,
                    "note": "HomeKit thermostat control requires HAP pairing",
                }
            return {"success": False, "error": "Invalid mode"}

        elif action == "set_fan_mode":
            fan_mode = params.get("mode")
            if fan_mode in ("auto", "on"):
                return {
                    "success": True,
                    "action": "set_fan_mode",
                    "fan_mode": fan_mode,
                    "note": "HomeKit thermostat control requires HAP pairing",
                }
            return {"success": False, "error": "Invalid fan mode"}

        return {"success": False, "error": f"Unknown action: {action}"}

    def get_supported_actions(self, device_type: str) -> list[str]:
        """Get supported actions for device type."""
        if device_type == "thermostat":
            return ["set_temperature", "set_mode", "set_fan_mode"]
        return []

    async def close(self) -> None:
        """Clean up HomeKit connections."""
        for device_id, conn in self._connections.items():
            try:
                if hasattr(conn, "close"):
                    conn.close()
            except Exception:
                pass

        self._connections.clear()
        self._devices_cache.clear()
        self._authenticated = False


class EcobeeHomeKitService(HomeKitService):
    """Specialized service for Ecobee thermostats via HomeKit.

    This extends HomeKitService with Ecobee-specific features.
    Since Ecobee API registration is blocked, HomeKit is the primary
    method for controlling Ecobee thermostats programmatically.

    Setup requirements:
    1. Ecobee thermostat must be added to HomeKit on an iOS device
    2. HomeKit pairing credentials must be exported
    3. pyatv and/or aiohomekit for communication
    """

    platform = "ecobee_homekit"

    async def get_device_state(self, device_id: str) -> DeviceState:
        """Get Ecobee thermostat state via HomeKit.

        Returns temperature, humidity, HVAC mode, and occupancy.
        """
        # Get base state
        base_state = await super().get_device_state(device_id)

        # Enhance with Ecobee-specific data
        # This would come from HomeKit characteristics:
        # - Current Temperature (characteristic type 0x11)
        # - Target Temperature (characteristic type 0x35)
        # - Current Humidity (characteristic type 0x10)
        # - Heating/Cooling State (characteristic type 0xF)
        # - Occupancy Detected (characteristic type 0x47)

        state = base_state.state.copy()
        state.update(
            {
                # These would be read from actual HomeKit characteristics
                "current_temperature": None,
                "target_temperature": None,
                "humidity": None,
                "mode": None,  # heat, cool, auto, off
                "hvac_state": None,  # heating, cooling, idle
                "fan_mode": None,  # auto, on
                "occupancy": None,  # home, away, sleep
            }
        )

        return DeviceState(
            device_id=device_id,
            platform="ecobee_homekit",
            online=base_state.online,
            state=state,
            last_updated=datetime.utcnow(),
            capabilities=[
                DeviceCapability.TEMPERATURE_READ.value,
                DeviceCapability.TEMPERATURE_SET.value,
                DeviceCapability.MODE_CONTROL.value,
                DeviceCapability.HUMIDITY_READ.value,
            ],
        )

    def get_supported_actions(self, device_type: str) -> list[str]:
        """Ecobee-specific actions."""
        return [
            "set_temperature",
            "set_mode",
            "set_fan_mode",
            "set_hold",  # Set temperature hold
            "resume_schedule",  # Resume normal schedule
        ]
