"""Home device manager - orchestrates all home automation services."""

from typing import Any, Optional

import structlog

from .base import (
    AuthenticationError,
    BaseHomeService,
    DeviceEvent,
    DeviceState,
)

logger = structlog.get_logger(__name__)


class HomeDeviceManager:
    """Orchestrates all home automation platform services.

    Provides a unified interface for managing devices across multiple
    platforms (Ring, LG ThinQ, Bosch, Apple, etc.).
    """

    # Registry of available service classes - populated by imports
    _service_classes: dict[str, type[BaseHomeService]] = {}

    def __init__(self):
        """Initialize the device manager."""
        self._services: dict[str, BaseHomeService] = {}
        self._logger = logger.bind(component="home_device_manager")

    @classmethod
    def register_service(cls, platform: str, service_class: type[BaseHomeService]):
        """Register a service class for a platform.

        Args:
            platform: Platform identifier (e.g., "ring", "lg_thinq").
            service_class: The service class to register.
        """
        cls._service_classes[platform] = service_class
        logger.info("service_registered", platform=platform)

    @property
    def available_platforms(self) -> list[str]:
        """Get list of available (registered) platforms."""
        return list(self._service_classes.keys())

    @property
    def connected_platforms(self) -> list[str]:
        """Get list of currently connected platforms."""
        return list(self._services.keys())

    async def initialize_service(
        self, platform: str, credentials: dict[str, Any]
    ) -> BaseHomeService:
        """Initialize and authenticate a platform service.

        Args:
            platform: Platform identifier.
            credentials: Platform-specific credentials.

        Returns:
            Initialized and authenticated service.

        Raises:
            ValueError: If platform is not registered.
            AuthenticationError: If authentication fails.
        """
        if platform not in self._service_classes:
            available = ", ".join(self._service_classes.keys()) or "none"
            raise ValueError(f"Unknown platform: {platform}. Available platforms: {available}")

        self._logger.info("initializing_service", platform=platform)

        service_class = self._service_classes[platform]
        service = service_class(credentials)

        try:
            authenticated = await service.authenticate()
            if not authenticated:
                raise AuthenticationError(f"Failed to authenticate with {platform}")

            self._services[platform] = service
            self._logger.info("service_initialized", platform=platform)
            return service

        except Exception as e:
            self._logger.error("service_initialization_failed", platform=platform, error=str(e))
            raise

    def get_service(self, platform: str) -> Optional[BaseHomeService]:
        """Get an initialized service by platform.

        Args:
            platform: Platform identifier.

        Returns:
            The service if connected, None otherwise.
        """
        return self._services.get(platform)

    def is_connected(self, platform: str) -> bool:
        """Check if a platform is connected.

        Args:
            platform: Platform identifier.

        Returns:
            True if connected.
        """
        return platform in self._services

    async def disconnect_service(self, platform: str) -> bool:
        """Disconnect and remove a platform service.

        Args:
            platform: Platform identifier.

        Returns:
            True if disconnected, False if wasn't connected.
        """
        if platform not in self._services:
            return False

        service = self._services.pop(platform)
        await service.close()
        self._logger.info("service_disconnected", platform=platform)
        return True

    async def discover_all_devices(self) -> dict[str, list[dict[str, Any]]]:
        """Discover devices across all connected platforms.

        Returns:
            Dict mapping platform to list of discovered devices.
        """
        results = {}

        for platform, service in self._services.items():
            try:
                devices = await service.discover_devices()
                results[platform] = devices
                self._logger.info("devices_discovered", platform=platform, count=len(devices))
            except Exception as e:
                self._logger.error("discovery_failed", platform=platform, error=str(e))
                results[platform] = []

        return results

    async def get_device_state(self, platform: str, device_id: str) -> DeviceState:
        """Get current state of a device.

        Args:
            platform: Platform identifier.
            device_id: Device identifier.

        Returns:
            Current device state.

        Raises:
            ValueError: If platform not connected.
            DeviceNotFoundError: If device not found.
        """
        service = self._services.get(platform)
        if not service:
            raise ValueError(f"Platform {platform} is not connected")

        return await service.get_device_state(device_id)

    async def get_all_device_states(self) -> list[DeviceState]:
        """Get current state of all devices across all platforms.

        Returns:
            List of device states.
        """
        states = []

        for platform, service in self._services.items():
            try:
                devices = await service.discover_devices()
                for device in devices:
                    try:
                        state = await service.get_device_state(device["device_id"])
                        states.append(state)
                    except Exception as e:
                        self._logger.warning(
                            "state_fetch_failed",
                            platform=platform,
                            device_id=device.get("device_id"),
                            error=str(e),
                        )
            except Exception as e:
                self._logger.error("platform_state_fetch_failed", platform=platform, error=str(e))

        return states

    async def execute_action(
        self, platform: str, device_id: str, action: str, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Execute an action on a device.

        Args:
            platform: Platform identifier.
            device_id: Device identifier.
            action: Action to execute.
            params: Action parameters.

        Returns:
            Action result dict.

        Raises:
            ValueError: If platform not connected.
        """
        service = self._services.get(platform)
        if not service:
            return {"success": False, "error": f"Platform {platform} is not connected"}

        try:
            result = await service.execute_action(device_id, action, params or {})
            self._logger.info(
                "action_executed",
                platform=platform,
                device_id=device_id,
                action=action,
                success=result.get("success", False),
            )
            return result
        except Exception as e:
            self._logger.error(
                "action_failed", platform=platform, device_id=device_id, action=action, error=str(e)
            )
            return {"success": False, "error": str(e)}

    async def get_recent_events(
        self, platform: str, device_id: str, limit: int = 10
    ) -> list[DeviceEvent]:
        """Get recent events from a device.

        Args:
            platform: Platform identifier.
            device_id: Device identifier.
            limit: Maximum events to return.

        Returns:
            List of events.
        """
        service = self._services.get(platform)
        if not service:
            return []

        try:
            return await service.get_recent_events(device_id, limit)
        except Exception as e:
            self._logger.error(
                "events_fetch_failed", platform=platform, device_id=device_id, error=str(e)
            )
            return []

    async def health_check_all(self) -> dict[str, bool]:
        """Check health of all connected services.

        Returns:
            Dict mapping platform to health status.
        """
        results = {}
        for platform, service in self._services.items():
            results[platform] = await service.health_check()
        return results

    async def close_all(self) -> None:
        """Close all service connections."""
        for platform in list(self._services.keys()):
            await self.disconnect_service(platform)

    def get_platform_status(self) -> list[dict[str, Any]]:
        """Get status of all platforms (available and connected).

        Returns:
            List of platform status dicts.
        """
        platforms = []

        # All registered platforms
        for platform in self._service_classes.keys():
            platforms.append(
                {
                    "id": platform,
                    "name": self._get_platform_display_name(platform),
                    "available": True,
                    "connected": platform in self._services,
                }
            )

        return platforms

    def _get_platform_display_name(self, platform: str) -> str:
        """Get human-readable platform name."""
        names = {
            "ring": "Ring",
            "lg_thinq": "LG ThinQ",
            "bosch": "Bosch Home Connect",
            "homekit": "HomeKit (Ecobee)",
            "apple_media": "Apple TV/HomePod",
        }
        return names.get(platform, platform.replace("_", " ").title())


# Global instance
device_manager = HomeDeviceManager()
