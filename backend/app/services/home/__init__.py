"""Home automation services package."""

from .apple_media import AppleMediaService
from .automation import AutomationBuilder, AutomationEngine, automation_engine
from .base import BaseHomeService, DeviceCapability, DeviceEvent, DeviceState
from .bosch import BoschHomeConnectService
from .homekit import EcobeeHomeKitService, HomeKitService
from .lg_thinq import LGThinQService
from .manager import HomeDeviceManager, device_manager

# Import service implementations
from .ring import RingService

# Register all services with the manager
HomeDeviceManager.register_service("ring", RingService)
HomeDeviceManager.register_service("lg_thinq", LGThinQService)
HomeDeviceManager.register_service("bosch", BoschHomeConnectService)
HomeDeviceManager.register_service("apple_media", AppleMediaService)
HomeDeviceManager.register_service("homekit", HomeKitService)
HomeDeviceManager.register_service("ecobee_homekit", EcobeeHomeKitService)

__all__ = [
    "BaseHomeService",
    "DeviceState",
    "DeviceEvent",
    "DeviceCapability",
    "HomeDeviceManager",
    "device_manager",
    "RingService",
    "LGThinQService",
    "BoschHomeConnectService",
    "AppleMediaService",
    "HomeKitService",
    "EcobeeHomeKitService",
    "AutomationEngine",
    "AutomationBuilder",
    "automation_engine",
]
