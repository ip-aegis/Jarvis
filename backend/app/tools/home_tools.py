"""
LLM tools for home automation device control and monitoring.
Provides read-only and action tools for smart home devices.
"""
from datetime import datetime, timedelta
from typing import Optional

from app.database import SessionLocal
from app.models import HomeDevice, HomeEvent
from app.tools.base import ActionCategory, ActionTool, ActionType, Tool, tool_registry

# =============================================================================
# Global Home Device Manager instance (use singleton from services)
# =============================================================================


async def get_home_manager():
    """Get the home device manager singleton."""
    from app.services.home import device_manager

    return device_manager


# =============================================================================
# Read-Only Tools
# =============================================================================


async def list_home_devices_handler(
    device_type: Optional[str] = None,
    room: Optional[str] = None,
    platform: Optional[str] = None,
) -> dict:
    """List all home automation devices with optional filters."""
    db = SessionLocal()
    try:
        query = db.query(HomeDevice)

        if device_type:
            query = query.filter(HomeDevice.device_type == device_type)
        if room:
            query = query.filter(HomeDevice.room == room)
        if platform:
            query = query.filter(HomeDevice.platform == platform)

        devices = query.all()

        return {
            "devices": [
                {
                    "id": d.id,
                    "device_id": d.device_id,
                    "name": d.name,
                    "device_type": d.device_type,
                    "platform": d.platform,
                    "room": d.room,
                    "model": d.model,
                    "status": d.status,
                    "capabilities": d.capabilities or [],
                    "state": d.state or {},
                    "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                }
                for d in devices
            ],
            "total": len(devices),
        }
    finally:
        db.close()


async def get_home_device_status_handler(
    device_id: Optional[int] = None,
    name: Optional[str] = None,
) -> dict:
    """Get detailed status of a specific home device."""
    db = SessionLocal()
    try:
        if device_id:
            device = db.query(HomeDevice).filter_by(id=device_id).first()
        elif name:
            device = db.query(HomeDevice).filter(HomeDevice.name.ilike(f"%{name}%")).first()
        else:
            return {"error": "Must provide device_id or name"}

        if not device:
            return {"error": "Device not found"}

        # Try to get fresh state from the device
        manager = await get_home_manager()
        try:
            state = await manager.get_device_state(device.platform, device.device_id)
            fresh_state = state.state if state else device.state
        except Exception:
            fresh_state = device.state or {}

        result = {
            "id": device.id,
            "device_id": device.device_id,
            "name": device.name,
            "device_type": device.device_type,
            "platform": device.platform,
            "room": device.room,
            "model": device.model,
            "status": device.status,
            "capabilities": device.capabilities or [],
            "state": fresh_state,
            "last_seen": device.last_seen.isoformat() if device.last_seen else None,
        }

        # Add device-specific state interpretation
        if device.device_type in ("washer", "dryer", "dishwasher"):
            if fresh_state.get("cycle_state"):
                result["cycle_status"] = fresh_state.get("cycle_state")
            if fresh_state.get("remaining_time"):
                result["remaining_time"] = fresh_state.get("remaining_time")
            if fresh_state.get("progress"):
                result["progress_percent"] = fresh_state.get("progress")

        elif device.device_type == "thermostat":
            result["current_temperature"] = fresh_state.get("current_temperature")
            result["target_temperature"] = fresh_state.get("target_temperature")
            result["mode"] = fresh_state.get("mode")
            result["humidity"] = fresh_state.get("humidity")

        elif device.device_type in ("apple_tv", "homepod"):
            result["now_playing"] = {
                "title": fresh_state.get("title"),
                "artist": fresh_state.get("artist"),
                "album": fresh_state.get("album"),
                "playing": fresh_state.get("playing"),
                "paused": fresh_state.get("paused"),
            }

        elif device.device_type == "doorbell":
            result["last_ring"] = fresh_state.get("last_ring")
            result["last_motion"] = fresh_state.get("last_motion")
            result["battery_level"] = fresh_state.get("battery_level")

        return result
    finally:
        db.close()


async def get_home_events_handler(
    device_id: Optional[int] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 20,
    hours: int = 24,
) -> dict:
    """Get recent home automation events."""
    db = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        query = db.query(HomeEvent).filter(HomeEvent.occurred_at > since)

        if device_id:
            query = query.filter(HomeEvent.device_id == device_id)
        if event_type:
            query = query.filter(HomeEvent.event_type == event_type)
        if severity:
            query = query.filter(HomeEvent.severity == severity)

        events = query.order_by(HomeEvent.occurred_at.desc()).limit(limit).all()

        # Get device names for context
        device_names = {}
        for event in events:
            if event.device_id and event.device_id not in device_names:
                device = db.query(HomeDevice).filter_by(id=event.device_id).first()
                if device:
                    device_names[event.device_id] = device.name

        return {
            "events": [
                {
                    "id": e.id,
                    "event_id": str(e.event_id) if e.event_id else None,
                    "device_id": e.device_id,
                    "device_name": device_names.get(e.device_id, "Unknown"),
                    "event_type": e.event_type,
                    "severity": e.severity,
                    "title": e.title,
                    "message": e.message,
                    "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
                    "acknowledged": e.acknowledged,
                    "media_url": e.media_url,
                }
                for e in events
            ],
            "total": len(events),
            "period_hours": hours,
        }
    finally:
        db.close()


async def get_thermostat_status_handler(
    device_id: Optional[int] = None,
    name: Optional[str] = None,
) -> dict:
    """Get thermostat status including temperature, humidity, and mode."""
    db = SessionLocal()
    try:
        if device_id:
            device = db.query(HomeDevice).filter_by(id=device_id, device_type="thermostat").first()
        elif name:
            device = (
                db.query(HomeDevice)
                .filter(HomeDevice.name.ilike(f"%{name}%"), HomeDevice.device_type == "thermostat")
                .first()
            )
        else:
            # Get first thermostat
            device = db.query(HomeDevice).filter_by(device_type="thermostat").first()

        if not device:
            return {"error": "Thermostat not found"}

        state = device.state or {}

        return {
            "id": device.id,
            "name": device.name,
            "platform": device.platform,
            "current_temperature": state.get("current_temperature"),
            "target_temperature": state.get("target_temperature"),
            "humidity": state.get("humidity"),
            "mode": state.get("mode"),  # heat, cool, auto, off
            "hvac_state": state.get("hvac_state"),  # heating, cooling, idle
            "fan_mode": state.get("fan_mode"),
            "occupancy": state.get("occupancy"),
            "status": device.status,
        }
    finally:
        db.close()


async def get_now_playing_handler(
    device_id: Optional[int] = None,
    name: Optional[str] = None,
) -> dict:
    """Get now playing info from Apple TV or HomePod."""
    db = SessionLocal()
    try:
        if device_id:
            device = db.query(HomeDevice).filter_by(id=device_id).first()
        elif name:
            device = (
                db.query(HomeDevice)
                .filter(
                    HomeDevice.name.ilike(f"%{name}%"),
                    HomeDevice.device_type.in_(["apple_tv", "homepod"]),
                )
                .first()
            )
        else:
            # Get first media device
            device = (
                db.query(HomeDevice)
                .filter(HomeDevice.device_type.in_(["apple_tv", "homepod"]))
                .first()
            )

        if not device:
            return {"error": "Media device not found"}

        # Try to get fresh state
        manager = await get_home_manager()
        try:
            state_obj = await manager.get_device_state(device.platform, device.device_id)
            state = state_obj.state if state_obj else device.state or {}
        except Exception:
            state = device.state or {}

        return {
            "id": device.id,
            "name": device.name,
            "device_type": device.device_type,
            "power": state.get("power", False),
            "playing": state.get("playing", False),
            "paused": state.get("paused", False),
            "idle": state.get("idle", True),
            "media_type": state.get("media_type"),
            "title": state.get("title"),
            "artist": state.get("artist"),
            "album": state.get("album"),
            "genre": state.get("genre"),
            "position": state.get("position"),
            "total_time": state.get("total_time"),
            "shuffle": state.get("shuffle"),
            "repeat": state.get("repeat"),
            "volume": state.get("volume"),
        }
    finally:
        db.close()


async def get_appliance_status_handler(
    appliance_type: Optional[str] = None,
) -> dict:
    """Get status of all appliances (washer, dryer, dishwasher, etc.)."""
    db = SessionLocal()
    try:
        appliance_types = ["washer", "dryer", "dishwasher", "oven", "refrigerator"]

        if appliance_type:
            appliance_types = [appliance_type]

        devices = db.query(HomeDevice).filter(HomeDevice.device_type.in_(appliance_types)).all()

        result = {
            "appliances": [],
            "running_count": 0,
        }

        for device in devices:
            state = device.state or {}
            is_running = state.get("power", False) and (
                state.get("operation_state") in ("Run", "Running", "Active")
                or state.get("cycle_state") not in (None, "Off", "Complete", "Idle")
            )

            appliance_info = {
                "id": device.id,
                "name": device.name,
                "device_type": device.device_type,
                "platform": device.platform,
                "status": device.status,
                "power": state.get("power", False),
                "is_running": is_running,
                "operation_state": state.get("operation_state"),
                "cycle_state": state.get("cycle_state"),
                "remaining_time": state.get("remaining_time"),
                "progress": state.get("progress"),
                "door_open": state.get("door_open"),
            }

            result["appliances"].append(appliance_info)
            if is_running:
                result["running_count"] += 1

        return result
    finally:
        db.close()


# =============================================================================
# Action Tools (may require confirmation)
# =============================================================================


async def set_thermostat_handler(
    device_id: Optional[int] = None,
    name: Optional[str] = None,
    temperature: Optional[float] = None,
    mode: Optional[str] = None,
) -> dict:
    """Set thermostat temperature or mode."""
    db = SessionLocal()
    try:
        if device_id:
            device = db.query(HomeDevice).filter_by(id=device_id, device_type="thermostat").first()
        elif name:
            device = (
                db.query(HomeDevice)
                .filter(HomeDevice.name.ilike(f"%{name}%"), HomeDevice.device_type == "thermostat")
                .first()
            )
        else:
            device = db.query(HomeDevice).filter_by(device_type="thermostat").first()

        if not device:
            return {"error": "Thermostat not found"}

        manager = await get_home_manager()

        actions = []
        results = []

        if temperature is not None:
            result = await manager.execute_action(
                device.platform, device.device_id, "set_temperature", {"temperature": temperature}
            )
            results.append(result)
            actions.append(f"temperature to {temperature}")

        if mode is not None:
            result = await manager.execute_action(
                device.platform, device.device_id, "set_mode", {"mode": mode}
            )
            results.append(result)
            actions.append(f"mode to {mode}")

        success = all(r.get("success", False) for r in results)

        return {
            "success": success,
            "device": device.name,
            "actions": actions,
            "results": results,
        }
    finally:
        db.close()


async def control_media_handler(
    device_id: Optional[int] = None,
    name: Optional[str] = None,
    action: str = "play_pause",
    volume: Optional[int] = None,
) -> dict:
    """Control media playback on Apple TV or HomePod."""
    db = SessionLocal()
    try:
        if device_id:
            device = db.query(HomeDevice).filter_by(id=device_id).first()
        elif name:
            device = (
                db.query(HomeDevice)
                .filter(
                    HomeDevice.name.ilike(f"%{name}%"),
                    HomeDevice.device_type.in_(["apple_tv", "homepod"]),
                )
                .first()
            )
        else:
            device = (
                db.query(HomeDevice)
                .filter(HomeDevice.device_type.in_(["apple_tv", "homepod"]))
                .first()
            )

        if not device:
            return {"error": "Media device not found"}

        manager = await get_home_manager()

        valid_actions = [
            "play",
            "pause",
            "play_pause",
            "stop",
            "next",
            "previous",
            "volume_up",
            "volume_down",
            "turn_on",
            "turn_off",
            "home",
            "menu",
            "select",
        ]

        if action not in valid_actions:
            return {"error": f"Invalid action. Valid actions: {valid_actions}"}

        params = {}
        if action == "set_volume" and volume is not None:
            action = "set_volume"
            params["volume"] = volume

        result = await manager.execute_action(device.platform, device.device_id, action, params)

        return {
            "success": result.get("success", False),
            "device": device.name,
            "action": action,
            "error": result.get("error"),
        }
    finally:
        db.close()


async def start_appliance_handler(
    device_id: Optional[int] = None,
    name: Optional[str] = None,
    program: Optional[str] = None,
) -> dict:
    """Start an appliance cycle (washer, dishwasher, etc.)."""
    db = SessionLocal()
    try:
        if device_id:
            device = db.query(HomeDevice).filter_by(id=device_id).first()
        elif name:
            device = (
                db.query(HomeDevice)
                .filter(
                    HomeDevice.name.ilike(f"%{name}%"),
                    HomeDevice.device_type.in_(["washer", "dryer", "dishwasher"]),
                )
                .first()
            )
        else:
            return {"error": "Must specify device_id or name"}

        if not device:
            return {"error": "Appliance not found"}

        manager = await get_home_manager()

        params = {}
        if program:
            params["program"] = program
            params["course"] = program  # LG uses 'course'

        # Determine action based on platform
        if device.platform == "lg_thinq":
            action = "start_cycle"
        elif device.platform == "bosch":
            action = "start_program"
        else:
            action = "start_program"

        result = await manager.execute_action(device.platform, device.device_id, action, params)

        return {
            "success": result.get("success", False),
            "device": device.name,
            "device_type": device.device_type,
            "program": program or "default",
            "error": result.get("error"),
        }
    finally:
        db.close()


async def stop_appliance_handler(
    device_id: Optional[int] = None,
    name: Optional[str] = None,
) -> dict:
    """Stop or pause an appliance cycle."""
    db = SessionLocal()
    try:
        if device_id:
            device = db.query(HomeDevice).filter_by(id=device_id).first()
        elif name:
            device = db.query(HomeDevice).filter(HomeDevice.name.ilike(f"%{name}%")).first()
        else:
            return {"error": "Must specify device_id or name"}

        if not device:
            return {"error": "Appliance not found"}

        manager = await get_home_manager()

        # Try pause first, then stop
        result = await manager.execute_action(
            device.platform,
            device.device_id,
            "pause" if device.platform == "lg_thinq" else "pause_program",
            {},
        )

        if not result.get("success"):
            result = await manager.execute_action(
                device.platform,
                device.device_id,
                "stop" if device.platform == "lg_thinq" else "stop_program",
                {},
            )

        return {
            "success": result.get("success", False),
            "device": device.name,
            "action": "stopped/paused",
            "error": result.get("error"),
        }
    finally:
        db.close()


async def ring_snapshot_handler(
    device_id: Optional[int] = None,
    name: Optional[str] = None,
) -> dict:
    """Get a snapshot from a Ring doorbell or camera."""
    db = SessionLocal()
    try:
        if device_id:
            device = db.query(HomeDevice).filter_by(id=device_id).first()
        elif name:
            device = (
                db.query(HomeDevice)
                .filter(HomeDevice.name.ilike(f"%{name}%"), HomeDevice.platform == "ring")
                .first()
            )
        else:
            device = db.query(HomeDevice).filter_by(platform="ring", device_type="doorbell").first()

        if not device:
            return {"error": "Ring device not found"}

        manager = await get_home_manager()

        result = await manager.execute_action("ring", device.device_id, "get_snapshot", {})

        return {
            "success": result.get("success", False),
            "device": device.name,
            "snapshot_url": result.get("snapshot_url"),
            "error": result.get("error"),
        }
    finally:
        db.close()


# =============================================================================
# Tool Registrations
# =============================================================================


# Add HOME category to ActionCategory
class HomeActionCategory:
    HOME = "home"


# Read-only tools
list_home_devices_tool = Tool(
    name="list_home_devices",
    description="List all home automation devices (Ring, appliances, thermostats, media players). Can filter by device_type, room, or platform.",
    parameters={
        "type": "object",
        "properties": {
            "device_type": {
                "type": "string",
                "description": "Filter by type: doorbell, camera, washer, dryer, dishwasher, thermostat, apple_tv, homepod",
            },
            "room": {
                "type": "string",
                "description": "Filter by room name",
            },
            "platform": {
                "type": "string",
                "description": "Filter by platform: ring, lg_thinq, bosch, apple_media, homekit",
            },
        },
        "required": [],
    },
    handler=list_home_devices_handler,
)

get_home_device_status_tool = Tool(
    name="get_home_device_status",
    description="Get detailed status of a specific home device including current state, capabilities, and device-specific information.",
    parameters={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "integer",
                "description": "The device database ID",
            },
            "name": {
                "type": "string",
                "description": "The device name (partial match supported)",
            },
        },
        "required": [],
    },
    handler=get_home_device_status_handler,
)

get_home_events_tool = Tool(
    name="get_home_events",
    description="Get recent home automation events like doorbell rings, motion alerts, appliance completions, etc.",
    parameters={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "integer",
                "description": "Filter events for a specific device",
            },
            "event_type": {
                "type": "string",
                "description": "Filter by event type: ding, motion, cycle_complete, alert",
            },
            "severity": {
                "type": "string",
                "description": "Filter by severity: info, warning, alert",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum events to return (default: 20)",
            },
            "hours": {
                "type": "integer",
                "description": "Look back period in hours (default: 24)",
            },
        },
        "required": [],
    },
    handler=get_home_events_handler,
)

get_thermostat_status_tool = Tool(
    name="get_thermostat_status",
    description="Get thermostat status including current temperature, target temperature, humidity, and HVAC mode.",
    parameters={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "integer",
                "description": "The thermostat device ID",
            },
            "name": {
                "type": "string",
                "description": "The thermostat name",
            },
        },
        "required": [],
    },
    handler=get_thermostat_status_handler,
)

get_now_playing_tool = Tool(
    name="get_now_playing",
    description="Get what's currently playing on Apple TV or HomePod including title, artist, playback state, and volume.",
    parameters={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "integer",
                "description": "The media device ID",
            },
            "name": {
                "type": "string",
                "description": "The device name (e.g., 'Living Room Apple TV')",
            },
        },
        "required": [],
    },
    handler=get_now_playing_handler,
)

get_appliance_status_tool = Tool(
    name="get_appliance_status",
    description="Get status of home appliances (washer, dryer, dishwasher) including cycle state, remaining time, and progress.",
    parameters={
        "type": "object",
        "properties": {
            "appliance_type": {
                "type": "string",
                "description": "Filter by type: washer, dryer, dishwasher, oven, refrigerator",
            },
        },
        "required": [],
    },
    handler=get_appliance_status_handler,
)

# Action tools - these may require confirmation
set_thermostat_tool = ActionTool(
    name="set_thermostat",
    description="Set thermostat temperature or mode. Changes home climate settings.",
    parameters={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "integer",
                "description": "The thermostat device ID",
            },
            "name": {
                "type": "string",
                "description": "The thermostat name",
            },
            "temperature": {
                "type": "number",
                "description": "Target temperature in degrees (Fahrenheit)",
            },
            "mode": {
                "type": "string",
                "description": "HVAC mode: heat, cool, auto, off",
            },
        },
        "required": [],
    },
    handler=set_thermostat_handler,
    action_type=ActionType.WRITE,
    category=ActionCategory.SYSTEM,
    requires_confirmation=False,  # Temperature changes are generally safe
)

control_media_tool = ActionTool(
    name="control_media",
    description="Control media playback on Apple TV or HomePod. Supports play, pause, next, previous, volume.",
    parameters={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "integer",
                "description": "The media device ID",
            },
            "name": {
                "type": "string",
                "description": "The device name",
            },
            "action": {
                "type": "string",
                "description": "Action: play, pause, play_pause, stop, next, previous, volume_up, volume_down, turn_on, turn_off",
            },
            "volume": {
                "type": "integer",
                "description": "Volume level 0-100 (only for set_volume action)",
            },
        },
        "required": ["action"],
    },
    handler=control_media_handler,
    action_type=ActionType.WRITE,
    category=ActionCategory.SYSTEM,
    requires_confirmation=False,  # Media control is safe
)

start_appliance_tool = ActionTool(
    name="start_appliance",
    description="[REQUIRES CONFIRMATION] Start a washer, dryer, or dishwasher cycle. Make sure the appliance is loaded and ready.",
    parameters={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "integer",
                "description": "The appliance device ID",
            },
            "name": {
                "type": "string",
                "description": "The appliance name",
            },
            "program": {
                "type": "string",
                "description": "Program/cycle to run (e.g., 'Cotton', 'Auto', 'Normal')",
            },
        },
        "required": [],
    },
    handler=start_appliance_handler,
    action_type=ActionType.WRITE,
    category=ActionCategory.SYSTEM,
    requires_confirmation=True,
    confirmation_message="Start {program or 'default'} cycle on the appliance? Make sure it's loaded and ready.",
    target_type="home_device",
)

stop_appliance_tool = ActionTool(
    name="stop_appliance",
    description="Stop or pause a running appliance cycle.",
    parameters={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "integer",
                "description": "The appliance device ID",
            },
            "name": {
                "type": "string",
                "description": "The appliance name",
            },
        },
        "required": [],
    },
    handler=stop_appliance_handler,
    action_type=ActionType.WRITE,
    category=ActionCategory.SYSTEM,
    requires_confirmation=False,  # Stopping is generally safe
)

ring_snapshot_tool = Tool(
    name="ring_snapshot",
    description="Get a snapshot image from a Ring doorbell or camera.",
    parameters={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "integer",
                "description": "The Ring device ID",
            },
            "name": {
                "type": "string",
                "description": "The Ring device name",
            },
        },
        "required": [],
    },
    handler=ring_snapshot_handler,
)


# Register all tools
tool_registry.register(list_home_devices_tool)
tool_registry.register(get_home_device_status_tool)
tool_registry.register(get_home_events_tool)
tool_registry.register(get_thermostat_status_tool)
tool_registry.register(get_now_playing_tool)
tool_registry.register(get_appliance_status_tool)
tool_registry.register(set_thermostat_tool)
tool_registry.register(control_media_tool)
tool_registry.register(start_appliance_tool)
tool_registry.register(stop_appliance_tool)
tool_registry.register(ring_snapshot_tool)
