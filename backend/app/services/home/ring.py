"""Ring doorbell and camera service implementation."""

import asyncio
from datetime import datetime
from typing import Any, Optional

import structlog
from ring_doorbell import Auth, Ring

from .base import (
    AuthenticationError,
    BaseHomeService,
    DeviceCapability,
    DeviceConnectionError,
    DeviceEvent,
    DeviceNotFoundError,
    DeviceState,
)

logger = structlog.get_logger(__name__)


class RingService(BaseHomeService):
    """Service for Ring doorbell and camera devices.

    Uses the python-ring-doorbell library for API access.
    Requires initial authentication with username/password or refresh token.
    """

    platform = "ring"

    def __init__(self, credentials: dict[str, Any]):
        """Initialize Ring service.

        Args:
            credentials: Dict containing either:
                - refresh_token: Existing refresh token (preferred)
                - username + password: For initial auth (will prompt 2FA)
        """
        super().__init__(credentials)
        self._ring: Optional[Ring] = None
        self._auth: Optional[Auth] = None
        self._token_updated = False
        self._new_token: Optional[dict] = None

    def _token_update_callback(self, token: dict[str, Any]):
        """Called by Ring library when token is refreshed."""
        self._new_token = token
        self._token_updated = True
        self._logger.info("ring_token_refreshed")

    async def authenticate(self) -> bool:
        """Authenticate with Ring API.

        Returns:
            True if authentication successful.

        Raises:
            AuthenticationError: If auth fails or 2FA is required.
        """
        from ring_doorbell.exceptions import Requires2FAError

        def _do_auth():
            try:
                # Check if we have a refresh token (could be string or full token dict)
                refresh_token = self.credentials.get("refresh_token")
                token_dict = self.credentials.get("token")  # Full token dict if available

                if token_dict and isinstance(token_dict, dict):
                    # Use full token dict (preferred - contains access_token, refresh_token, etc.)
                    self._auth = Auth("Jarvis/1.0", token_dict, self._token_update_callback)
                    self._ring = Ring(self._auth)
                    self._ring.update_data()
                    return True
                elif refresh_token:
                    # Build token dict from refresh token string
                    # The Auth class expects a dict with at least 'refresh_token' key
                    if isinstance(refresh_token, str):
                        token_dict = {"refresh_token": refresh_token}
                    else:
                        token_dict = refresh_token  # Already a dict

                    self._auth = Auth("Jarvis/1.0", token_dict, self._token_update_callback)
                    self._ring = Ring(self._auth)
                    self._ring.update_data()
                    return True

                # Need username/password
                username = self.credentials.get("username")
                password = self.credentials.get("password")
                otp_code = self.credentials.get("otp_code")  # 2FA code if provided

                if not username or not password:
                    raise AuthenticationError(
                        "Ring requires either refresh_token or username/password"
                    )

                self._auth = Auth("Jarvis/1.0", None, self._token_update_callback)

                # Try to fetch token - this may raise Requires2FAError
                self._auth.fetch_token(username, password, otp_code)

                self._ring = Ring(self._auth)
                self._ring.update_data()

                self._logger.info("ring_auth_success")
                return True

            except Requires2FAError:
                raise AuthenticationError(
                    "2FA_REQUIRED: Ring sent a verification code to your email/phone. "
                    "Retry with the otp_code parameter included."
                )
            except AuthenticationError:
                raise
            except Exception as e:
                error_str = str(e)
                self._logger.error("ring_auth_failed", error=error_str, error_type=type(e).__name__)
                raise AuthenticationError(f"Ring authentication failed: {e}")

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, _do_auth)
            self._authenticated = result
            return result
        except AuthenticationError:
            raise
        except Exception as e:
            raise AuthenticationError(str(e))

    async def refresh_token(self) -> bool:
        """Refresh Ring OAuth token.

        Returns:
            True if refresh successful.
        """
        if not self._ring:
            return False

        def _refresh():
            try:
                self._ring.update_data()
                return True
            except Exception as e:
                self._logger.error("ring_token_refresh_failed", error=str(e))
                return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _refresh)

    def get_updated_token(self) -> Optional[dict[str, Any]]:
        """Get the updated token if it was refreshed.

        Returns:
            New token dict if updated, None otherwise.
        """
        if self._token_updated:
            self._token_updated = False
            return self._new_token
        return None

    async def discover_devices(self) -> list[dict[str, Any]]:
        """Discover all Ring devices.

        Returns:
            List of device dictionaries.
        """
        if not self._ring:
            raise DeviceConnectionError("Ring not authenticated")

        def _discover():
            self._ring.update_data()
            devices = []

            # Get all devices - newer API uses properties
            ring_devices = self._ring.devices()

            # Doorbells
            doorbells = getattr(ring_devices, "doorbells", []) or []

            for doorbell in doorbells:
                devices.append(
                    {
                        "device_id": str(doorbell.id),
                        "name": doorbell.name,
                        "device_type": "doorbell",
                        "model": doorbell.model,
                        "firmware": getattr(doorbell, "firmware", None),
                        "capabilities": [
                            DeviceCapability.RING.value,
                            DeviceCapability.MOTION_DETECT.value,
                            DeviceCapability.VIDEO_STREAM.value,
                            DeviceCapability.SNAPSHOT.value,
                            DeviceCapability.TWO_WAY_AUDIO.value,
                            DeviceCapability.BATTERY.value,
                        ],
                        "state": {
                            "battery_level": getattr(doorbell, "battery_life", None),
                            "is_online": getattr(doorbell, "is_connected", True),
                            "volume": getattr(doorbell, "volume", None),
                            "wifi_signal": getattr(doorbell, "wifi_signal_strength", None),
                        },
                    }
                )

            # Stickup cams / other cameras
            stickup_cams = getattr(ring_devices, "stickup_cams", []) or []

            for camera in stickup_cams:
                capabilities = [
                    DeviceCapability.MOTION_DETECT.value,
                    DeviceCapability.VIDEO_STREAM.value,
                    DeviceCapability.SNAPSHOT.value,
                ]

                # Check for additional capabilities
                if hasattr(camera, "has_battery") and camera.has_battery:
                    capabilities.append(DeviceCapability.BATTERY.value)

                devices.append(
                    {
                        "device_id": str(camera.id),
                        "name": camera.name,
                        "device_type": "camera",
                        "model": camera.model,
                        "firmware": getattr(camera, "firmware", None),
                        "capabilities": capabilities,
                        "state": {
                            "battery_level": getattr(camera, "battery_life", None),
                            "is_online": getattr(camera, "is_connected", True),
                        },
                    }
                )

            # Chimes
            chimes = getattr(ring_devices, "chimes", []) or []

            for chime in chimes:
                devices.append(
                    {
                        "device_id": str(chime.id),
                        "name": chime.name,
                        "device_type": "chime",
                        "model": chime.model,
                        "capabilities": ["chime"],
                        "state": {
                            "is_online": getattr(chime, "is_connected", True),
                            "volume": getattr(chime, "volume", None),
                        },
                    }
                )

            return devices

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _discover)

    async def get_device_state(self, device_id: str) -> DeviceState:
        """Get current state of a Ring device.

        Args:
            device_id: Ring device ID.

        Returns:
            Current device state.
        """
        if not self._ring:
            raise DeviceConnectionError("Ring not authenticated")

        def _get_state():
            self._ring.update_data()

            # Search all device types - newer API uses properties
            ring_devices = self._ring.devices()
            doorbells = getattr(ring_devices, "doorbells", []) or []
            stickup_cams = getattr(ring_devices, "stickup_cams", []) or []
            chimes = getattr(ring_devices, "chimes", []) or []

            all_devices = list(doorbells) + list(stickup_cams) + list(chimes)

            for device in all_devices:
                if str(device.id) == device_id:
                    device_type = "doorbell"
                    if device in stickup_cams:
                        device_type = "camera"
                    elif device in chimes:
                        device_type = "chime"

                    state = {
                        "battery_level": getattr(device, "battery_life", None),
                        "is_online": getattr(device, "is_connected", True),
                        "volume": getattr(device, "volume", None),
                        "wifi_signal": getattr(device, "wifi_signal_strength", None),
                    }

                    # Add last event times for doorbells
                    if device_type == "doorbell":
                        history = device.history(limit=1)
                        if history:
                            last_event = history[0]
                            created_at = last_event.get("created_at")
                            # Convert datetime to ISO string if needed
                            if hasattr(created_at, "isoformat"):
                                created_at = created_at.isoformat()
                            if last_event.get("kind") == "ding":
                                state["last_ring"] = created_at
                            elif last_event.get("kind") == "motion":
                                state["last_motion"] = created_at

                    capabilities = [DeviceCapability.MOTION_DETECT.value]
                    if device_type == "doorbell":
                        capabilities.extend(
                            [
                                DeviceCapability.RING.value,
                                DeviceCapability.VIDEO_STREAM.value,
                            ]
                        )

                    return DeviceState(
                        device_id=device_id,
                        platform="ring",
                        online=state.get("is_online", True),
                        state=state,
                        last_updated=datetime.utcnow(),
                        capabilities=capabilities,
                    )

            raise DeviceNotFoundError(f"Ring device {device_id} not found")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_state)

    async def execute_action(
        self, device_id: str, action: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute action on Ring device.

        Supported actions:
        - set_volume: Set doorbell/chime volume (volume: 0-10)
        - enable_motion: Enable/disable motion detection (enabled: bool)
        - get_snapshot: Get current snapshot URL

        Args:
            device_id: Ring device ID.
            action: Action name.
            params: Action parameters.

        Returns:
            Result dict.
        """
        if not self._ring:
            return {"success": False, "error": "Ring not authenticated"}

        def _execute():
            self._ring.update_data()

            ring_devices = self._ring.devices()
            doorbells = getattr(ring_devices, "doorbells", []) or []
            stickup_cams = getattr(ring_devices, "stickup_cams", []) or []
            chimes = getattr(ring_devices, "chimes", []) or []
            all_devices = list(doorbells) + list(stickup_cams) + list(chimes)

            for device in all_devices:
                if str(device.id) == device_id:
                    try:
                        if action == "set_volume":
                            volume = params.get("volume", 5)
                            device.volume = volume
                            return {"success": True, "volume": volume}

                        elif action == "enable_motion":
                            enabled = params.get("enabled", True)
                            if hasattr(device, "motion_detection"):
                                device.motion_detection = enabled
                                return {"success": True, "motion_enabled": enabled}
                            return {"success": False, "error": "Motion detection not supported"}

                        elif action == "get_snapshot":
                            # Get latest recording/snapshot
                            history = device.history(limit=1)
                            if history:
                                recording_id = history[0].get("id")
                                url = device.recording_url(recording_id)
                                event_type = history[0].get("kind", "unknown")
                                created_at = history[0].get("created_at", "")
                                return {
                                    "success": True,
                                    "snapshot_url": url,
                                    "event_type": event_type,
                                    "created_at": created_at,
                                }
                            return {"success": False, "error": "No recordings available"}

                        elif action == "get_recordings":
                            # Get multiple recent recordings
                            limit = params.get("limit", 5)
                            history = device.history(limit=limit)
                            recordings = []
                            for event in history:
                                try:
                                    recording_id = event.get("id")
                                    url = device.recording_url(recording_id)
                                    recordings.append(
                                        {
                                            "id": str(recording_id),
                                            "url": url,
                                            "created_at": event.get("created_at", ""),
                                            "type": event.get("kind", "unknown"),
                                        }
                                    )
                                except Exception:
                                    pass  # Skip if URL can't be fetched
                            return {"success": True, "recordings": recordings}

                        elif action == "get_live_snapshot":
                            # Request a new live snapshot using sync HTTP requests
                            import hashlib
                            import os
                            import time as time_module

                            import httpx

                            try:
                                # Get auth token - try new token first, then original credentials
                                token = self._new_token or self.credentials.get("token")
                                if not token or "access_token" not in token:
                                    return {
                                        "success": False,
                                        "error": "No valid auth token (need full token with access_token)",
                                    }

                                headers = {
                                    "Authorization": f"Bearer {token['access_token']}",
                                    "User-Agent": "Jarvis/1.0",
                                }

                                base_url = "https://api.ring.com"
                                device_ring_id = device.id

                                # Trigger a new snapshot
                                timestamp_url = f"{base_url}/clients_api/snapshots/timestamps"
                                payload = {"doorbot_ids": [device_ring_id]}

                                with httpx.Client(timeout=30.0) as client:
                                    # First request triggers the snapshot
                                    client.post(timestamp_url, json=payload, headers=headers)
                                    request_time = time_module.time()

                                    # Poll for new snapshot (3 retries, 2 second delay)
                                    snapshot_bytes = None
                                    for attempt in range(3):
                                        time_module.sleep(2)
                                        resp = client.post(
                                            timestamp_url, json=payload, headers=headers
                                        )
                                        if resp.status_code == 200:
                                            data = resp.json()
                                            timestamps = data.get("timestamps", [])
                                            if (
                                                timestamps
                                                and timestamps[0].get("timestamp", 0) / 1000
                                                > request_time
                                            ):
                                                # New snapshot is ready, fetch it
                                                snapshot_url = f"{base_url}/clients_api/snapshots/image/{device_ring_id}"
                                                snap_resp = client.get(
                                                    snapshot_url, headers=headers
                                                )
                                                if snap_resp.status_code == 200:
                                                    snapshot_bytes = snap_resp.content
                                                    break

                                if snapshot_bytes:
                                    # Generate unique filename
                                    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                                    snapshot_id = hashlib.md5(
                                        f"{device_id}_{timestamp}".encode()
                                    ).hexdigest()[:12]
                                    filename = f"ring_snapshot_{device_id}_{snapshot_id}.jpg"

                                    # Store snapshot
                                    snapshot_dir = "/tmp/ring_snapshots"
                                    os.makedirs(snapshot_dir, exist_ok=True)
                                    filepath = os.path.join(snapshot_dir, filename)

                                    with open(filepath, "wb") as f:
                                        f.write(snapshot_bytes)

                                    # Clean up old snapshots (keep last 50)
                                    try:
                                        files = sorted(
                                            [
                                                os.path.join(snapshot_dir, f)
                                                for f in os.listdir(snapshot_dir)
                                            ],
                                            key=os.path.getmtime,
                                        )
                                        for old_file in files[:-50]:
                                            os.remove(old_file)
                                    except Exception:
                                        pass

                                    return {
                                        "success": True,
                                        "snapshot_id": snapshot_id,
                                        "filename": filename,
                                        "device_name": device.name,
                                        "timestamp": datetime.utcnow().isoformat(),
                                    }
                                else:
                                    return {
                                        "success": False,
                                        "error": "Camera did not return snapshot (may need Snapshot Capture enabled in Ring app)",
                                    }

                            except Exception as e:
                                return {
                                    "success": False,
                                    "error": f"Failed to get snapshot: {str(e)}",
                                }

                        elif action == "get_live_stream_url":
                            # Note: Live streaming requires additional setup
                            return {"success": False, "error": "Live streaming not yet implemented"}

                        else:
                            return {"success": False, "error": f"Unknown action: {action}"}

                    except Exception as e:
                        return {"success": False, "error": str(e)}

            return {"success": False, "error": f"Device {device_id} not found"}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _execute)

    async def get_recent_events(self, device_id: str, limit: int = 10) -> list[DeviceEvent]:
        """Get recent events from a Ring device.

        Args:
            device_id: Ring device ID.
            limit: Maximum events to return.

        Returns:
            List of DeviceEvent objects.
        """
        if not self._ring:
            return []

        def _get_events():
            self._ring.update_data()
            events = []

            ring_devices = self._ring.devices()
            doorbells = getattr(ring_devices, "doorbells", []) or []
            stickup_cams = getattr(ring_devices, "stickup_cams", []) or []
            all_devices = list(doorbells) + list(stickup_cams)

            for device in all_devices:
                if str(device.id) == device_id:
                    try:
                        history = device.history(limit=limit)
                        for event in history:
                            event_type = event.get("kind", "unknown")
                            title = f"Ring {event_type}"

                            if event_type == "ding":
                                title = "Doorbell Ring"
                                severity = "alert"
                            elif event_type == "motion":
                                title = "Motion Detected"
                                severity = "info"
                            else:
                                severity = "info"

                            # Get recording URL
                            media_url = None
                            try:
                                media_url = device.recording_url(event.get("id"))
                            except Exception:
                                pass

                            created_at = event.get("created_at")
                            if isinstance(created_at, str):
                                occurred_at = datetime.fromisoformat(
                                    created_at.replace("Z", "+00:00")
                                )
                            else:
                                occurred_at = datetime.utcnow()

                            events.append(
                                DeviceEvent(
                                    device_id=device_id,
                                    event_type=event_type,
                                    title=title,
                                    message=f"{event_type.capitalize()} at {device.name}",
                                    data=event,
                                    occurred_at=occurred_at,
                                    severity=severity,
                                    media_url=media_url,
                                )
                            )
                    except Exception as e:
                        logger.warning("ring_events_fetch_failed", error=str(e))

                    break

            return events

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_events)

    def get_supported_actions(self, device_type: str) -> list[str]:
        """Get supported actions for device type."""
        if device_type == "doorbell":
            return [
                "set_volume",
                "enable_motion",
                "get_snapshot",
                "get_recordings",
                "get_live_snapshot",
            ]
        elif device_type == "camera":
            return ["enable_motion", "get_snapshot", "get_recordings", "get_live_snapshot"]
        elif device_type == "chime":
            return ["set_volume"]
        return []

    async def close(self) -> None:
        """Clean up Ring connection."""
        self._ring = None
        self._auth = None
        self._authenticated = False
