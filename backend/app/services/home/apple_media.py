"""Apple TV and HomePod service implementation using pyatv."""

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


class AppleMediaService(BaseHomeService):
    """Service for Apple TV and HomePod devices.

    Uses the pyatv library for local network control.
    Supports playback control, now playing info, and volume control.
    """

    platform = "apple_media"

    def __init__(self, credentials: dict[str, Any]):
        """Initialize Apple Media service.

        Args:
            credentials: Dict containing:
                - credentials: Dict mapping device_id to pairing credentials
                - scan_timeout: Network scan timeout in seconds (default: 5)
        """
        super().__init__(credentials)
        self._devices_cache: dict[str, Any] = {}
        self._connections: dict[str, Any] = {}
        self._pairing_sessions: dict[str, Any] = {}
        self._scan_timeout = credentials.get("scan_timeout", 5)

    async def authenticate(self) -> bool:
        """Authenticate (scan for devices on network).

        Apple TV/HomePod use local network discovery, not cloud auth.
        """
        try:
            import pyatv

            # Scan for devices
            devices = await pyatv.scan(asyncio.get_event_loop(), timeout=self._scan_timeout)

            for device in devices:
                self._devices_cache[device.identifier] = device

            self._authenticated = True
            self._logger.info("apple_media_scan_complete", devices_found=len(devices))
            return True

        except ImportError:
            raise AuthenticationError("pyatv not installed. Run: pip install pyatv")
        except Exception as e:
            self._logger.error("apple_scan_failed", error=str(e))
            raise AuthenticationError(f"Apple device scan failed: {e}")

    async def discover_devices(self) -> list[dict[str, Any]]:
        """Discover Apple TV and HomePod devices on network."""
        try:
            import pyatv

            # Rescan network
            devices = await pyatv.scan(asyncio.get_event_loop(), timeout=self._scan_timeout)

            result = []
            for device in devices:
                self._devices_cache[device.identifier] = device

                # Determine device type from model
                model_info = device.device_info.model if device.device_info else None
                model = str(model_info) if model_info else ""
                if "HomePod" in model:
                    device_type = "homepod"
                else:
                    device_type = "apple_tv"

                # Get capabilities based on protocols
                capabilities = [DeviceCapability.PLAYBACK_CONTROL.value]
                for service in device.services:
                    if service.protocol.name == "AirPlay":
                        capabilities.append(DeviceCapability.AIRPLAY.value)
                    if service.protocol.name == "Companion":
                        capabilities.append(DeviceCapability.VOLUME_CONTROL.value)

                capabilities.append(DeviceCapability.NOW_PLAYING.value)

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
            self._logger.error("apple_discovery_failed", error=str(e))
            return []

    async def start_pairing(self, device_id: str, protocol: str = "companion") -> dict[str, Any]:
        """Start pairing process with an Apple device.

        Args:
            device_id: Device identifier.
            protocol: Protocol to pair (companion, airplay, mrp).

        Returns:
            Dict with pairing_id and instructions.
        """
        try:
            import pyatv
            from pyatv.const import Protocol

            # Get device config
            device_config = self._devices_cache.get(device_id)
            if not device_config:
                devices = await pyatv.scan(
                    asyncio.get_event_loop(), identifier=device_id, timeout=self._scan_timeout
                )
                if not devices:
                    return {"success": False, "error": f"Device {device_id} not found"}
                device_config = devices[0]
                self._devices_cache[device_id] = device_config

            # Map protocol string to enum
            protocol_map = {
                "companion": Protocol.Companion,
                "airplay": Protocol.AirPlay,
                "mrp": Protocol.MRP,
                "raop": Protocol.RAOP,
            }
            proto = protocol_map.get(protocol.lower(), Protocol.Companion)

            # Start pairing
            pairing = await pyatv.pair(device_config, proto, asyncio.get_event_loop())
            await pairing.begin()

            # Store pairing session
            pairing_id = f"{device_id}_{protocol}"
            self._pairing_sessions[pairing_id] = pairing

            self._logger.info(
                "apple_pairing_started",
                device_id=device_id,
                protocol=protocol,
                requires_pin=pairing.device_provides_pin,
            )

            if pairing.device_provides_pin:
                return {
                    "success": True,
                    "pairing_id": pairing_id,
                    "requires_pin": True,
                    "message": "Enter the PIN shown on your Apple device screen",
                }
            else:
                return {
                    "success": True,
                    "pairing_id": pairing_id,
                    "requires_pin": False,
                    "message": "Check your Apple device for a pairing request",
                }

        except Exception as e:
            self._logger.error("apple_pairing_start_failed", device_id=device_id, error=str(e))
            return {"success": False, "error": str(e)}

    async def finish_pairing(self, pairing_id: str, pin: Optional[str] = None) -> dict[str, Any]:
        """Complete pairing with PIN.

        Args:
            pairing_id: ID from start_pairing.
            pin: PIN from Apple device screen (if required).

        Returns:
            Dict with credentials on success.
        """
        try:
            pairing = self._pairing_sessions.get(pairing_id)
            if not pairing:
                return {"success": False, "error": "Pairing session not found or expired"}

            # Provide PIN if required
            if pin:
                pairing.pin(pin)

            # Complete pairing
            await pairing.finish()

            # Get credentials
            if pairing.has_paired:
                credentials = pairing.service.credentials

                # Store credentials
                device_id = pairing_id.split("_")[0]
                protocol = pairing_id.split("_")[1] if "_" in pairing_id else "companion"

                if "credentials" not in self.credentials:
                    self.credentials["credentials"] = {}
                if device_id not in self.credentials["credentials"]:
                    self.credentials["credentials"][device_id] = {}
                self.credentials["credentials"][device_id][protocol] = credentials

                self._logger.info("apple_pairing_complete", device_id=device_id, protocol=protocol)

                # Clean up session
                await pairing.close()
                del self._pairing_sessions[pairing_id]

                return {
                    "success": True,
                    "device_id": device_id,
                    "protocol": protocol,
                    "credentials": credentials,
                    "message": "Pairing successful! Device is now ready to control.",
                }
            else:
                await pairing.close()
                del self._pairing_sessions[pairing_id]
                return {"success": False, "error": "Pairing was not completed"}

        except Exception as e:
            self._logger.error("apple_pairing_finish_failed", pairing_id=pairing_id, error=str(e))
            # Clean up session on error
            if pairing_id in self._pairing_sessions:
                try:
                    await self._pairing_sessions[pairing_id].close()
                except Exception:
                    pass
                del self._pairing_sessions[pairing_id]
            return {"success": False, "error": str(e)}

    async def cancel_pairing(self, pairing_id: str) -> dict[str, Any]:
        """Cancel an in-progress pairing session."""
        pairing = self._pairing_sessions.get(pairing_id)
        if pairing:
            try:
                await pairing.close()
            except Exception:
                pass
            del self._pairing_sessions[pairing_id]
            return {"success": True, "message": "Pairing cancelled"}
        return {"success": False, "error": "No active pairing session"}

    async def get_device_state(self, device_id: str) -> DeviceState:
        """Get current state of an Apple device."""
        try:
            import pyatv

            # Get device config
            device_config = self._devices_cache.get(device_id)

            if not device_config:
                # Rescan
                devices = await pyatv.scan(
                    asyncio.get_event_loop(), identifier=device_id, timeout=self._scan_timeout
                )
                if not devices:
                    raise DeviceNotFoundError(f"Apple device {device_id} not found")
                device_config = devices[0]
                self._devices_cache[device_id] = device_config

            # Connect to device
            atv = await self._get_connection(device_id, device_config)

            if not atv:
                return DeviceState(
                    device_id=device_id,
                    platform="apple_media",
                    online=False,
                    state={},
                    last_updated=datetime.utcnow(),
                    capabilities=[],
                )

            try:
                # Get now playing info
                playing = await atv.metadata.playing()

                # Get power state safely
                power_on = True
                try:
                    if hasattr(atv, "power") and atv.power:
                        power_on = atv.power.power_state.name == "On"
                except Exception:
                    pass  # Power state not supported, assume on

                state = {
                    "power": power_on,
                    "playing": playing.device_state.name == "Playing",
                    "paused": playing.device_state.name == "Paused",
                    "idle": playing.device_state.name == "Idle",
                    "media_type": playing.media_type.name if playing.media_type else None,
                    "title": playing.title,
                    "artist": playing.artist,
                    "album": playing.album,
                    "genre": playing.genre,
                    "position": playing.position,
                    "total_time": playing.total_time,
                    "shuffle": playing.shuffle.name if playing.shuffle else None,
                    "repeat": playing.repeat.name if playing.repeat else None,
                }

                # Get volume if available
                if hasattr(atv, "audio") and atv.audio:
                    try:
                        state["volume"] = atv.audio.volume
                    except Exception:
                        pass

                # Determine device type
                model_info = device_config.device_info.model if device_config.device_info else None
                model = str(model_info) if model_info else ""
                device_type = "homepod" if "HomePod" in model else "apple_tv"

                capabilities = [
                    DeviceCapability.PLAYBACK_CONTROL.value,
                    DeviceCapability.NOW_PLAYING.value,
                ]
                if hasattr(atv, "audio"):
                    capabilities.append(DeviceCapability.VOLUME_CONTROL.value)

                return DeviceState(
                    device_id=device_id,
                    platform="apple_media",
                    online=True,
                    state=state,
                    last_updated=datetime.utcnow(),
                    capabilities=capabilities,
                )

            except Exception as e:
                self._logger.warning("apple_state_failed", device_id=device_id, error=str(e))
                return DeviceState(
                    device_id=device_id,
                    platform="apple_media",
                    online=False,
                    state={},
                    last_updated=datetime.utcnow(),
                    capabilities=[],
                )

        except Exception as e:
            self._logger.error("apple_state_error", device_id=device_id, error=str(e))
            raise DeviceConnectionError(str(e))

    async def execute_action(
        self, device_id: str, action: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute action on Apple device.

        Supported actions:
        - play: Start/resume playback
        - pause: Pause playback
        - play_pause: Toggle play/pause
        - stop: Stop playback
        - next: Skip to next track
        - previous: Go to previous track
        - volume_up: Increase volume
        - volume_down: Decrease volume
        - set_volume: Set volume level (volume: 0-100)
        - turn_on: Turn on device
        - turn_off: Turn off device
        - home: Go to home screen
        - menu: Show menu
        - select: Select current item

        Args:
            device_id: Apple device identifier.
            action: Action name.
            params: Action parameters.

        Returns:
            Result dict.
        """
        try:
            import pyatv

            device_config = self._devices_cache.get(device_id)

            if not device_config:
                devices = await pyatv.scan(
                    asyncio.get_event_loop(), identifier=device_id, timeout=self._scan_timeout
                )
                if not devices:
                    return {"success": False, "error": f"Device {device_id} not found"}
                device_config = devices[0]

            atv = await self._get_connection(device_id, device_config)

            if not atv:
                return {"success": False, "error": "Could not connect to device"}

            try:
                rc = atv.remote_control

                if action == "play":
                    await rc.play()
                elif action == "pause":
                    await rc.pause()
                elif action == "play_pause":
                    await rc.play_pause()
                elif action == "stop":
                    await rc.stop()
                elif action == "next":
                    await rc.next()
                elif action == "previous":
                    await rc.previous()
                elif action == "volume_up":
                    await rc.volume_up()
                elif action == "volume_down":
                    await rc.volume_down()
                elif action == "set_volume":
                    volume = params.get("volume")
                    if volume is not None and hasattr(atv, "audio"):
                        await atv.audio.set_volume(float(volume))
                    else:
                        return {"success": False, "error": "Volume control not available"}
                elif action == "turn_on":
                    if hasattr(atv, "power"):
                        await atv.power.turn_on()
                    else:
                        return {"success": False, "error": "Power control not available"}
                elif action == "turn_off":
                    if hasattr(atv, "power"):
                        await atv.power.turn_off()
                    else:
                        return {"success": False, "error": "Power control not available"}
                elif action == "home":
                    await rc.home()
                elif action == "menu":
                    await rc.menu()
                elif action == "select":
                    await rc.select()
                elif action == "up":
                    await rc.up()
                elif action == "down":
                    await rc.down()
                elif action == "left":
                    await rc.left()
                elif action == "right":
                    await rc.right()
                else:
                    return {"success": False, "error": f"Unknown action: {action}"}

                return {"success": True, "action": action}

            except Exception as e:
                return {"success": False, "error": str(e)}

        except Exception as e:
            self._logger.error("apple_action_failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def _get_connection(self, device_id: str, device_config: Any) -> Optional[Any]:
        """Get or create connection to Apple device."""
        import pyatv

        # Check for existing connection
        if device_id in self._connections:
            conn = self._connections[device_id]
            # Verify connection is still valid
            try:
                await conn.metadata.playing()
                return conn
            except Exception:
                # Connection stale, remove it
                try:
                    conn.close()
                except Exception:
                    pass
                del self._connections[device_id]

        # Create new connection
        try:
            # Get stored credentials if any
            stored_creds = self.credentials.get("credentials", {})
            device_creds = stored_creds.get(device_id)

            if device_creds:
                # Load credentials for this device
                for protocol, cred_data in device_creds.items():
                    try:
                        proto = getattr(pyatv.Protocol, protocol)
                        device_config.set_credentials(proto, cred_data)
                    except Exception:
                        pass

            atv = await pyatv.connect(device_config, asyncio.get_event_loop())
            self._connections[device_id] = atv
            return atv

        except Exception as e:
            self._logger.warning("apple_connect_failed", device_id=device_id, error=str(e))
            return None

    def get_supported_actions(self, device_type: str) -> list[str]:
        """Get supported actions for device type."""
        base_actions = [
            "play",
            "pause",
            "play_pause",
            "stop",
            "next",
            "previous",
            "volume_up",
            "volume_down",
            "set_volume",
        ]

        if device_type == "apple_tv":
            return base_actions + [
                "turn_on",
                "turn_off",
                "home",
                "menu",
                "select",
                "up",
                "down",
                "left",
                "right",
            ]
        elif device_type == "homepod":
            return base_actions

        return base_actions

    async def close(self) -> None:
        """Clean up Apple device connections."""
        for device_id, conn in self._connections.items():
            try:
                conn.close()
            except Exception:
                pass

        self._connections.clear()
        self._devices_cache.clear()
        self._authenticated = False
