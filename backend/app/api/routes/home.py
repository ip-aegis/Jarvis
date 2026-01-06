"""
Home automation API routes.
Supports Ring, LG ThinQ, Bosch, HomeKit/Ecobee, and Apple TV/HomePod.
"""
import uuid
from datetime import datetime
from typing import Any, Optional

import httpx
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database import get_db
from app.models import (
    HomeAutomation,
    HomeDevice,
    HomeDeviceCredential,
    HomeEvent,
    HomePlatformCredential,
)
from app.services.home.manager import device_manager

logger = get_logger(__name__)

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class PlatformCredentials(BaseModel):
    """Platform authentication credentials."""

    platform: str = Field(..., description="ring, lg_thinq, bosch, homekit, apple_media")
    credentials: dict[str, Any] = Field(..., description="Platform-specific credentials")


class DeviceActionRequest(BaseModel):
    """Request to execute an action on a device."""

    action: str = Field(..., description="Action to execute (e.g., play, pause, set_temperature)")
    params: Optional[dict[str, Any]] = Field(default={}, description="Action parameters")


class DeviceUpdateRequest(BaseModel):
    """Request to update device metadata."""

    name: Optional[str] = None
    room: Optional[str] = None
    zone: Optional[str] = None


class AutomationCreateRequest(BaseModel):
    """Request to create an automation rule."""

    name: str
    description: Optional[str] = None
    trigger_type: str = Field(..., description="event, schedule, condition, device_state")
    trigger_config: dict[str, Any]
    conditions: Optional[list[dict[str, Any]]] = []
    actions: list[dict[str, Any]]
    enabled: bool = True
    cooldown_seconds: int = 0


class HomeDeviceResponse(BaseModel):
    """Home device response model."""

    id: int
    device_id: str
    name: str
    device_type: str
    platform: str
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    room: Optional[str] = None
    zone: Optional[str] = None
    status: str
    state: Optional[dict[str, Any]] = None
    capabilities: Optional[list[str]] = None
    last_seen: Optional[datetime] = None

    class Config:
        from_attributes = True


class HomeEventResponse(BaseModel):
    """Home event response model."""

    id: int
    event_id: str
    device_id: int
    event_type: str
    severity: str
    title: str
    message: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    media_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    occurred_at: datetime
    acknowledged: bool

    class Config:
        from_attributes = True


class HomeAutomationResponse(BaseModel):
    """Home automation response model."""

    id: int
    automation_id: str
    name: str
    description: Optional[str] = None
    trigger_type: str
    trigger_config: dict[str, Any]
    conditions: Optional[list[dict[str, Any]]] = None
    actions: list[dict[str, Any]]
    enabled: bool
    cooldown_seconds: int
    trigger_count: int
    last_triggered: Optional[datetime] = None

    class Config:
        from_attributes = True


class PlatformStatusResponse(BaseModel):
    """Platform status response model."""

    id: str
    name: str
    available: bool
    connected: bool


# =============================================================================
# Platform Management
# =============================================================================


@router.get("/platforms", response_model=dict[str, list[PlatformStatusResponse]])
async def list_platforms():
    """List all supported platforms and their connection status."""
    platforms = device_manager.get_platform_status()
    return {"platforms": platforms}


@router.post("/platforms/connect")
async def connect_platform(
    request: PlatformCredentials,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Connect to a home automation platform and discover devices.

    This will:
    1. Authenticate with the platform
    2. Discover all available devices
    3. Save devices to the database
    4. Return the list of discovered devices
    """
    try:
        # Load saved credentials from database for this platform
        credentials = dict(request.credentials)

        # For Apple Media, load device pairing credentials
        if request.platform == "apple_media":
            saved_creds = {}
            device_creds = (
                db.query(HomeDeviceCredential)
                .join(HomeDevice)
                .filter(HomeDevice.platform == "apple_media")
                .all()
            )
            for cred in device_creds:
                if cred.auth_data:
                    device = db.query(HomeDevice).filter(HomeDevice.id == cred.device_id).first()
                    if device:
                        saved_creds[device.device_id] = cred.auth_data
            if saved_creds:
                credentials["credentials"] = saved_creds
                logger.info(
                    "loaded_saved_credentials", platform="apple_media", count=len(saved_creds)
                )

        # Initialize and authenticate
        service = await device_manager.initialize_service(request.platform, credentials)

        # Discover devices
        discovered = await service.discover_devices()

        # Save platform credentials
        platform_cred = (
            db.query(HomePlatformCredential)
            .filter(HomePlatformCredential.platform == request.platform)
            .first()
        )

        if platform_cred:
            platform_cred.connected = True
            platform_cred.auth_data = request.credentials
            platform_cred.updated_at = datetime.utcnow()
        else:
            platform_cred = HomePlatformCredential(
                platform=request.platform,
                auth_data=request.credentials,
                connected=True,
            )
            db.add(platform_cred)

        # For Ring, check if we got a refresh token and save it
        if request.platform == "ring":
            token_data = None

            if hasattr(service, "get_updated_token"):
                token_data = service.get_updated_token()

            if not token_data and hasattr(service, "_auth") and service._auth:
                # Try to get token from auth object
                try:
                    token_data = service._auth.token
                except Exception:
                    pass

            if token_data and "refresh_token" in token_data:
                platform_cred.refresh_token = token_data["refresh_token"]
                # Save full token dict for complete auth info
                platform_cred.auth_data = {"token": token_data}
                logger.info("ring_token_saved", has_access_token="access_token" in token_data)

        # Save discovered devices
        saved_devices = []
        for device_data in discovered:
            # Check if device already exists
            existing = (
                db.query(HomeDevice)
                .filter(HomeDevice.device_id == device_data["device_id"])
                .first()
            )

            if existing:
                # Update existing device
                existing.name = device_data.get("name", existing.name)
                existing.model = device_data.get("model", existing.model)
                existing.capabilities = device_data.get("capabilities", existing.capabilities)
                existing.state = device_data.get("state", existing.state)
                existing.status = "online"
                existing.last_seen = datetime.utcnow()
                existing.updated_at = datetime.utcnow()
                saved_devices.append(existing)
            else:
                # Create new device
                device = HomeDevice(
                    device_id=device_data["device_id"],
                    name=device_data.get("name", "Unknown Device"),
                    device_type=device_data.get("device_type", "unknown"),
                    platform=request.platform,
                    model=device_data.get("model"),
                    firmware_version=device_data.get("firmware"),
                    capabilities=device_data.get("capabilities", []),
                    state=device_data.get("state", {}),
                    status="online",
                    last_seen=datetime.utcnow(),
                )
                db.add(device)
                saved_devices.append(device)

        db.commit()

        logger.info(
            "platform_connected", platform=request.platform, devices_discovered=len(saved_devices)
        )

        return {
            "status": "connected",
            "platform": request.platform,
            "devices_discovered": len(saved_devices),
            "devices": [
                {
                    "id": d.id,
                    "device_id": d.device_id,
                    "name": d.name,
                    "type": d.device_type,
                }
                for d in saved_devices
            ],
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("platform_connection_failed", platform=request.platform)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/platforms/{platform}/save-token")
async def save_platform_token(
    platform: str,
    db: Session = Depends(get_db),
):
    """Save the current platform token to database (for Ring after successful auth)."""
    service = device_manager.get_service(platform)
    if not service:
        raise HTTPException(status_code=404, detail=f"Platform {platform} not connected")

    # For Ring, extract and save the refresh token
    if platform == "ring":
        try:
            token_data = None

            # Try get_updated_token first
            if hasattr(service, "get_updated_token"):
                token_data = service.get_updated_token()

            # Try _auth.token
            if not token_data and hasattr(service, "_auth") and service._auth:
                token_data = getattr(service._auth, "token", None)

            if token_data and "refresh_token" in token_data:
                platform_cred = (
                    db.query(HomePlatformCredential)
                    .filter(HomePlatformCredential.platform == platform)
                    .first()
                )

                if platform_cred:
                    # Save refresh_token string for backward compatibility
                    platform_cred.refresh_token = token_data["refresh_token"]
                    # Also save full token dict in auth_data for complete token info
                    platform_cred.auth_data = {"token": token_data}
                    platform_cred.updated_at = datetime.utcnow()
                    db.commit()
                    return {"status": "saved", "message": "Token saved successfully"}

            return {"status": "no_token", "message": "No refresh token available to save"}

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=400, detail=f"Token saving not supported for {platform}")


@router.post("/platforms/{platform}/disconnect")
async def disconnect_platform(
    platform: str,
    db: Session = Depends(get_db),
):
    """Disconnect from a platform."""
    disconnected = await device_manager.disconnect_service(platform)

    if disconnected:
        # Update platform credentials
        platform_cred = (
            db.query(HomePlatformCredential)
            .filter(HomePlatformCredential.platform == platform)
            .first()
        )
        if platform_cred:
            platform_cred.connected = False
            platform_cred.updated_at = datetime.utcnow()
            db.commit()

        return {"status": "disconnected", "platform": platform}

    raise HTTPException(status_code=404, detail=f"Platform {platform} was not connected")


# =============================================================================
# Device Management
# =============================================================================


@router.get("/devices", response_model=dict[str, Any])
async def list_devices(
    device_type: Optional[str] = None,
    platform: Optional[str] = None,
    room: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all home devices with optional filtering."""
    query = db.query(HomeDevice)

    if device_type:
        query = query.filter(HomeDevice.device_type == device_type)
    if platform:
        query = query.filter(HomeDevice.platform == platform)
    if room:
        query = query.filter(HomeDevice.room == room)
    if status:
        query = query.filter(HomeDevice.status == status)

    devices = query.order_by(HomeDevice.name).all()

    return {
        "devices": [
            {
                "id": d.id,
                "device_id": d.device_id,
                "name": d.name,
                "device_type": d.device_type,
                "platform": d.platform,
                "model": d.model,
                "room": d.room,
                "zone": d.zone,
                "status": d.status,
                "state": d.state,
                "capabilities": d.capabilities,
                "last_seen": d.last_seen.isoformat() if d.last_seen else None,
            }
            for d in devices
        ],
        "count": len(devices),
    }


@router.get("/devices/{device_id}", response_model=HomeDeviceResponse)
async def get_device(
    device_id: int,
    refresh: bool = False,
    db: Session = Depends(get_db),
):
    """Get detailed device information.

    Args:
        device_id: Database ID of the device.
        refresh: If true, fetch fresh state from the device.
    """
    device = db.query(HomeDevice).filter(HomeDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Optionally refresh state from service
    if refresh:
        service = device_manager.get_service(device.platform)
        if service:
            try:
                state = await service.get_device_state(device.device_id)
                device.state = state.state
                device.status = "online" if state.online else "offline"
                device.last_seen = state.last_updated
                db.commit()
            except Exception as e:
                logger.warning("device_refresh_failed", device_id=device_id, error=str(e))

    return device


@router.post("/devices/{device_id}/action")
async def execute_device_action(
    device_id: int,
    request: DeviceActionRequest,
    db: Session = Depends(get_db),
):
    """Execute an action on a device."""
    device = db.query(HomeDevice).filter(HomeDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    result = await device_manager.execute_action(
        device.platform, device.device_id, request.action, request.params or {}
    )

    if result.get("success"):
        # Update device state if action was successful
        device.last_seen = datetime.utcnow()
        db.commit()

    return result


@router.get("/media/proxy")
async def proxy_media(
    url: str = Query(..., description="Media URL to proxy"),
):
    """Proxy media (video/image) from external sources to avoid CORS issues.

    Ring and other services return signed URLs that may have CORS restrictions.
    This endpoint fetches the media and streams it to the frontend.
    """
    # Validate URL is from known sources (Ring API and Amazon CDN)
    allowed_domains = [
        "download-us-east-1.prod.phoenix.devices.amazon.dev",
        "download-us-east-2.prod.phoenix.devices.amazon.dev",
        "download-us-west-2.prod.phoenix.devices.amazon.dev",
        "download-eu-west-1.prod.phoenix.devices.amazon.dev",
        "download-eu-central-1.prod.phoenix.devices.amazon.dev",
        "download-ap-southeast-2.prod.phoenix.devices.amazon.dev",
        "ring.com",
        "api.ring.com",
        "fw.ring.com",
        "amazon.com",
        "amazonaws.com",
        "cloudfront.net",
    ]

    from urllib.parse import urlparse

    parsed = urlparse(url)
    if not any(domain in parsed.netloc for domain in allowed_domains):
        logger.warning("media_proxy_blocked", url=url[:100], domain=parsed.netloc)
        raise HTTPException(status_code=400, detail=f"URL not from allowed source: {parsed.netloc}")

    try:
        # First, fetch the URL and check response before streaming
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            response = await client.get(url)

            if response.status_code != 200:
                logger.error("media_fetch_failed", status=response.status_code, url=url[:100])
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to fetch media: {response.status_code}",
                )

            # Get content type from response headers or guess from URL
            content_type = response.headers.get("content-type", "video/mp4")
            if not content_type or content_type == "application/octet-stream":
                # Guess based on URL
                if ".jpg" in url.lower() or ".jpeg" in url.lower():
                    content_type = "image/jpeg"
                elif ".png" in url.lower():
                    content_type = "image/png"
                else:
                    content_type = "video/mp4"

            return StreamingResponse(
                iter([response.content]),
                media_type=content_type,
                headers={
                    "Content-Disposition": "inline",
                    "Cache-Control": "max-age=300",
                    "Content-Length": str(len(response.content)),
                },
            )
    except httpx.RequestError as e:
        logger.error("media_proxy_failed", url=url[:100], error=str(e))
        raise HTTPException(status_code=502, detail=f"Failed to fetch media: {str(e)}")


@router.get("/snapshots/{filename}")
async def get_snapshot(filename: str):
    """Serve a stored snapshot image.

    Snapshots are stored in /tmp/ring_snapshots by the get_live_snapshot action.
    """
    import os
    import re

    # Validate filename format to prevent path traversal
    if not re.match(r"^ring_snapshot_\d+_[a-f0-9]+\.jpg$", filename):
        raise HTTPException(status_code=400, detail="Invalid snapshot filename")

    snapshot_dir = "/tmp/ring_snapshots"
    filepath = os.path.join(snapshot_dir, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Snapshot not found")

    # Read and return the image
    with open(filepath, "rb") as f:
        content = f.read()

    return StreamingResponse(
        iter([content]),
        media_type="image/jpeg",
        headers={
            "Content-Disposition": f"inline; filename={filename}",
            "Cache-Control": "max-age=60",
            "Content-Length": str(len(content)),
        },
    )


@router.patch("/devices/{device_id}")
async def update_device(
    device_id: int,
    request: DeviceUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update device metadata (name, room, zone)."""
    device = db.query(HomeDevice).filter(HomeDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if request.name is not None:
        device.name = request.name
    if request.room is not None:
        device.room = request.room
    if request.zone is not None:
        device.zone = request.zone

    device.updated_at = datetime.utcnow()
    db.commit()

    return {"status": "updated", "device_id": device_id}


@router.delete("/devices/{device_id}")
async def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
):
    """Remove a device from Jarvis (does not affect the actual device)."""
    device = db.query(HomeDevice).filter(HomeDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    db.delete(device)
    db.commit()

    return {"status": "deleted", "device_id": device_id}


# =============================================================================
# Device Pairing (Apple devices)
# =============================================================================


class PairingStartRequest(BaseModel):
    """Request to start pairing with an Apple device."""

    protocol: str = Field(
        default="companion", description="Protocol to pair: companion, airplay, mrp"
    )


class PairingFinishRequest(BaseModel):
    """Request to finish pairing with PIN."""

    pairing_id: str = Field(..., description="Pairing ID from start_pairing")
    pin: Optional[str] = Field(None, description="PIN from device screen")


@router.post("/devices/{device_id}/pair/start")
async def start_device_pairing(
    device_id: int,
    request: PairingStartRequest,
    db: Session = Depends(get_db),
):
    """Start pairing process with an Apple device.

    This will initiate pairing and a PIN will appear on your Apple TV/HomePod screen.
    Use the finish endpoint with that PIN to complete pairing.
    """
    device = db.query(HomeDevice).filter(HomeDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if device.platform != "apple_media":
        raise HTTPException(status_code=400, detail="Pairing only supported for Apple devices")

    service = device_manager.get_service("apple_media")
    if not service:
        raise HTTPException(status_code=503, detail="Apple Media service not connected")

    result = await service.start_pairing(device.device_id, request.protocol)
    return result


@router.post("/devices/{device_id}/pair/finish")
async def finish_device_pairing(
    device_id: int,
    request: PairingFinishRequest,
    db: Session = Depends(get_db),
):
    """Complete pairing with the PIN from the device screen."""
    device = db.query(HomeDevice).filter(HomeDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if device.platform != "apple_media":
        raise HTTPException(status_code=400, detail="Pairing only supported for Apple devices")

    service = device_manager.get_service("apple_media")
    if not service:
        raise HTTPException(status_code=503, detail="Apple Media service not connected")

    result = await service.finish_pairing(request.pairing_id, request.pin)

    # If successful, save credentials to database
    if result.get("success") and result.get("credentials"):
        cred = (
            db.query(HomeDeviceCredential)
            .filter(HomeDeviceCredential.device_id == device.id)
            .first()
        )

        if cred:
            if cred.auth_data is None:
                cred.auth_data = {}
            cred.auth_data[result.get("protocol", "companion")] = result["credentials"]
            cred.updated_at = datetime.utcnow()
        else:
            cred = HomeDeviceCredential(
                device_id=device.id,
                platform=device.platform,
                auth_data={result.get("protocol", "companion"): result["credentials"]},
            )
            db.add(cred)

        db.commit()
        logger.info("device_credentials_saved", device_id=device_id)

    return result


@router.post("/devices/{device_id}/pair/cancel")
async def cancel_device_pairing(
    device_id: int,
    pairing_id: str,
    db: Session = Depends(get_db),
):
    """Cancel an in-progress pairing session."""
    device = db.query(HomeDevice).filter(HomeDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    service = device_manager.get_service("apple_media")
    if not service:
        raise HTTPException(status_code=503, detail="Apple Media service not connected")

    result = await service.cancel_pairing(pairing_id)
    return result


# =============================================================================
# Events
# =============================================================================


@router.get("/events", response_model=dict[str, Any])
async def list_events(
    device_id: Optional[int] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    unacknowledged_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List recent home automation events."""
    query = db.query(HomeEvent).order_by(HomeEvent.occurred_at.desc())

    if device_id:
        query = query.filter(HomeEvent.device_id == device_id)
    if event_type:
        query = query.filter(HomeEvent.event_type == event_type)
    if severity:
        query = query.filter(HomeEvent.severity == severity)
    if unacknowledged_only:
        query = query.filter(HomeEvent.acknowledged == False)

    total = query.count()
    events = query.offset(offset).limit(limit).all()

    return {
        "events": [
            {
                "id": e.id,
                "event_id": str(e.event_id),
                "device_id": e.device_id,
                "event_type": e.event_type,
                "severity": e.severity,
                "title": e.title,
                "message": e.message,
                "data": e.data,
                "media_url": e.media_url,
                "thumbnail_url": e.thumbnail_url,
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
                "acknowledged": e.acknowledged,
            }
            for e in events
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/events/{event_id}/acknowledge")
async def acknowledge_event(
    event_id: str,
    db: Session = Depends(get_db),
):
    """Acknowledge an event."""
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event ID format")

    event = db.query(HomeEvent).filter(HomeEvent.event_id == event_uuid).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    event.acknowledged = True
    event.acknowledged_at = datetime.utcnow()
    db.commit()

    return {"status": "acknowledged", "event_id": event_id}


@router.post("/events/acknowledge-all")
async def acknowledge_all_events(
    device_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Acknowledge all unacknowledged events."""
    query = db.query(HomeEvent).filter(HomeEvent.acknowledged == False)

    if device_id:
        query = query.filter(HomeEvent.device_id == device_id)

    count = query.update(
        {
            HomeEvent.acknowledged: True,
            HomeEvent.acknowledged_at: datetime.utcnow(),
        }
    )
    db.commit()

    return {"status": "acknowledged", "count": count}


# =============================================================================
# Automations
# =============================================================================


@router.get("/automations", response_model=dict[str, Any])
async def list_automations(
    enabled_only: bool = False,
    db: Session = Depends(get_db),
):
    """List all automation rules."""
    query = db.query(HomeAutomation)

    if enabled_only:
        query = query.filter(HomeAutomation.enabled == True)

    automations = query.order_by(HomeAutomation.name).all()

    return {
        "automations": [
            {
                "id": a.id,
                "automation_id": str(a.automation_id),
                "name": a.name,
                "description": a.description,
                "trigger_type": a.trigger_type,
                "trigger_config": a.trigger_config,
                "conditions": a.conditions,
                "actions": a.actions,
                "enabled": a.enabled,
                "cooldown_seconds": a.cooldown_seconds,
                "trigger_count": a.trigger_count,
                "last_triggered": a.last_triggered.isoformat() if a.last_triggered else None,
            }
            for a in automations
        ],
        "count": len(automations),
    }


@router.post("/automations")
async def create_automation(
    request: AutomationCreateRequest,
    db: Session = Depends(get_db),
):
    """Create a new automation rule."""
    automation = HomeAutomation(
        name=request.name,
        description=request.description,
        trigger_type=request.trigger_type,
        trigger_config=request.trigger_config,
        conditions=request.conditions,
        actions=request.actions,
        enabled=request.enabled,
        cooldown_seconds=request.cooldown_seconds,
    )
    db.add(automation)
    db.commit()
    db.refresh(automation)

    logger.info(
        "automation_created", automation_id=str(automation.automation_id), name=automation.name
    )

    return {
        "status": "created",
        "automation_id": str(automation.automation_id),
    }


@router.get("/automations/{automation_id}", response_model=HomeAutomationResponse)
async def get_automation(
    automation_id: str,
    db: Session = Depends(get_db),
):
    """Get automation details."""
    try:
        automation_uuid = uuid.UUID(automation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid automation ID format")

    automation = (
        db.query(HomeAutomation).filter(HomeAutomation.automation_id == automation_uuid).first()
    )

    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")

    return automation


@router.patch("/automations/{automation_id}")
async def update_automation(
    automation_id: str,
    enabled: Optional[bool] = None,
    name: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Update automation (enable/disable, rename)."""
    try:
        automation_uuid = uuid.UUID(automation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid automation ID format")

    automation = (
        db.query(HomeAutomation).filter(HomeAutomation.automation_id == automation_uuid).first()
    )

    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")

    if enabled is not None:
        automation.enabled = enabled
    if name is not None:
        automation.name = name

    automation.updated_at = datetime.utcnow()
    db.commit()

    return {"status": "updated", "automation_id": automation_id}


@router.delete("/automations/{automation_id}")
async def delete_automation(
    automation_id: str,
    db: Session = Depends(get_db),
):
    """Delete an automation rule."""
    try:
        automation_uuid = uuid.UUID(automation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid automation ID format")

    automation = (
        db.query(HomeAutomation).filter(HomeAutomation.automation_id == automation_uuid).first()
    )

    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")

    db.delete(automation)
    db.commit()

    return {"status": "deleted", "automation_id": automation_id}


# =============================================================================
# WebSocket for Real-time Events
# =============================================================================

# Store active WebSocket connections
_websocket_connections: list[WebSocket] = []


@router.websocket("/ws")
async def home_websocket(websocket: WebSocket):
    """WebSocket for real-time home automation events."""
    await websocket.accept()
    _websocket_connections.append(websocket)

    try:
        while True:
            # Keep connection alive and handle client messages
            data = await websocket.receive_text()
            # Could handle subscription requests here

    except WebSocketDisconnect:
        _websocket_connections.remove(websocket)
    except Exception as e:
        logger.warning("websocket_error", error=str(e))
        if websocket in _websocket_connections:
            _websocket_connections.remove(websocket)


async def broadcast_event(event: dict[str, Any]):
    """Broadcast an event to all connected WebSocket clients."""
    for ws in _websocket_connections:
        try:
            await ws.send_json(event)
        except Exception:
            pass


# =============================================================================
# Device Refresh (Background Task)
# =============================================================================


async def refresh_all_device_states(db: Session):
    """Background task to refresh all device states."""
    devices = db.query(HomeDevice).filter(HomeDevice.status != "unavailable").all()

    for device in devices:
        service = device_manager.get_service(device.platform)
        if service:
            try:
                state = await service.get_device_state(device.device_id)
                device.state = state.state
                device.status = "online" if state.online else "offline"
                device.last_seen = state.last_updated
            except Exception as e:
                logger.warning("device_refresh_failed", device_id=device.id, error=str(e))

    db.commit()
