"""
Action management API routes.
Handles action confirmation, audit logs, and scheduled actions.
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database import get_db
from app.models import ActionAudit, ScheduledAction
from app.services.actions import ActionService, action_registry

logger = get_logger(__name__)

router = APIRouter()
action_service = ActionService()


# =============================================================================
# Request/Response Models
# =============================================================================


class ConfirmActionRequest(BaseModel):
    """Request to confirm a pending action."""

    action_id: str
    confirmed_by: str = "api_user"


class CancelActionRequest(BaseModel):
    """Request to cancel a pending action."""

    cancelled_by: str = "api_user"


class ScheduleActionRequest(BaseModel):
    """Request to schedule an action."""

    name: Optional[str] = None
    action_name: str
    parameters: dict[str, Any] = {}
    schedule_type: str  # 'once', 'cron', 'interval', 'conditional'
    schedule_config: dict[str, Any] = {}
    # For conditional actions
    condition_expression: Optional[str] = None


class ExecuteActionRequest(BaseModel):
    """Request to execute an action directly."""

    action_name: str
    parameters: dict[str, Any] = {}
    user_id: str = "api_user"
    session_id: str = "api_session"
    natural_input: str = ""


# =============================================================================
# Confirmation Endpoints
# =============================================================================


@router.post("/confirm")
async def confirm_action(
    request: ConfirmActionRequest,
    db: Session = Depends(get_db),
):
    """Confirm a pending action and execute it."""
    result = await action_service.confirm_action(
        action_id=request.action_id,
        confirmed_by=request.confirmed_by,
        db=db,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "status": "confirmed",
        "action_id": result.action_id,
        "result": result.data,
    }


@router.post("/cancel/{action_id}")
async def cancel_action(
    action_id: str,
    request: CancelActionRequest = None,
    db: Session = Depends(get_db),
):
    """Cancel a pending action."""
    cancelled_by = request.cancelled_by if request else "api_user"

    result = await action_service.cancel_action(
        action_id=action_id,
        cancelled_by=cancelled_by,
        db=db,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "status": "cancelled",
        "action_id": action_id,
    }


@router.get("/pending")
async def list_pending_confirmations(db: Session = Depends(get_db)):
    """List all pending action confirmations."""
    pending = await action_service.get_pending_confirmations(db)
    return {"pending": pending}


@router.post("/cleanup-expired")
async def cleanup_expired_confirmations(db: Session = Depends(get_db)):
    """Clean up expired confirmation requests."""
    count = await action_service.cleanup_expired_confirmations(db)
    return {"status": "cleaned", "expired_count": count}


# =============================================================================
# Audit Log Endpoints
# =============================================================================


@router.get("/audit")
async def get_audit_log(
    limit: int = 50,
    action_type: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get action audit log with optional filters."""
    audit_log = await action_service.get_audit_log(
        db=db,
        limit=limit,
        action_type=action_type,
        status=status,
        category=category,
    )
    return {"audit_log": audit_log}


@router.get("/audit/{action_id}")
async def get_audit_entry(action_id: str, db: Session = Depends(get_db)):
    """Get a specific audit entry."""
    import uuid

    try:
        action_uuid = uuid.UUID(action_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid action ID format")

    audit = db.query(ActionAudit).filter(ActionAudit.action_id == action_uuid).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit entry not found")

    return {
        "action_id": str(audit.action_id),
        "action_name": audit.action_name,
        "action_type": audit.action_type,
        "category": audit.category,
        "parameters": audit.parameters,
        "target_type": audit.target_type,
        "target_id": audit.target_id,
        "target_name": audit.target_name,
        "initiated_by": audit.initiated_by,
        "session_id": audit.session_id,
        "natural_language_input": audit.natural_language_input,
        "llm_interpretation": audit.llm_interpretation,
        "initiated_at": audit.initiated_at.isoformat() if audit.initiated_at else None,
        "completed_at": audit.completed_at.isoformat() if audit.completed_at else None,
        "status": audit.status,
        "result": audit.result,
        "error_message": audit.error_message,
        "confirmation_required": audit.confirmation_required,
        "confirmed_by": audit.confirmed_by,
        "confirmed_at": audit.confirmed_at.isoformat() if audit.confirmed_at else None,
        "rollback_available": audit.rollback_available,
        "rollback_executed": audit.rollback_executed,
        "rollback_at": audit.rollback_at.isoformat() if audit.rollback_at else None,
        "rollback_result": audit.rollback_result,
    }


# =============================================================================
# Rollback Endpoints
# =============================================================================


@router.post("/rollback/{action_id}")
async def rollback_action(
    action_id: str,
    db: Session = Depends(get_db),
):
    """Rollback a completed action if rollback is available."""
    result = await action_service.rollback_action(
        action_id=action_id,
        rolled_back_by="api_user",
        db=db,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "status": "rolled_back",
        "action_id": action_id,
        "result": result.data,
    }


# =============================================================================
# Direct Execution Endpoints (for testing)
# =============================================================================


@router.post("/execute")
async def execute_action(
    request: ExecuteActionRequest,
    db: Session = Depends(get_db),
):
    """Execute an action directly (primarily for testing)."""
    result = await action_service.execute_action(
        action_name=request.action_name,
        parameters=request.parameters,
        user_id=request.user_id,
        session_id=request.session_id,
        natural_input=request.natural_input,
        db=db,
    )

    if result.requires_confirmation:
        return {
            "status": "confirmation_required",
            "action_id": result.action_id,
            "confirmation_prompt": result.confirmation_prompt,
            "affected_resources": result.affected_resources,
            "data": result.data,
        }

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "status": "executed",
        "action_id": result.action_id,
        "result": result.data,
    }


@router.get("/available")
async def list_available_actions():
    """List all available registered actions."""
    actions = action_registry.list_actions()
    return {
        "actions": [
            {
                "name": a.name,
                "description": a.description,
                "action_type": a.action_type.value,
                "category": a.category.value,
                "requires_confirmation": a.requires_confirmation,
                "has_rollback": a.rollback_handler is not None,
            }
            for a in actions
        ]
    }


# =============================================================================
# Scheduled Actions Endpoints
# =============================================================================


@router.get("/scheduled")
async def list_scheduled_actions(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all scheduled actions."""
    query = db.query(ScheduledAction)

    if status:
        query = query.filter(ScheduledAction.status == status)
    else:
        query = query.filter(ScheduledAction.status.in_(["active", "paused"]))

    scheduled = query.order_by(ScheduledAction.created_at.desc()).all()

    return {
        "scheduled": [
            {
                "id": s.id,
                "job_id": s.job_id,
                "name": s.name,
                "action_name": s.action_name,
                "parameters": s.parameters,
                "schedule_type": s.schedule_type,
                "schedule_config": s.schedule_config,
                "condition_expression": s.condition_expression,
                "status": s.status,
                "enabled": s.enabled,
                "next_run": s.next_run.isoformat() if s.next_run else None,
                "last_run": s.last_run.isoformat() if s.last_run else None,
                "run_count": s.run_count,
                "error_count": s.error_count,
                "created_by": s.created_by,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in scheduled
        ]
    }


@router.post("/scheduled")
async def create_scheduled_action(
    request: ScheduleActionRequest,
    db: Session = Depends(get_db),
):
    """Create a new scheduled action."""
    import uuid

    # Verify action exists
    action = action_registry.get(request.action_name)
    if not action:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.action_name}")

    job_id = f"scheduled_{request.action_name}_{uuid.uuid4().hex[:8]}"

    scheduled = ScheduledAction(
        job_id=job_id,
        name=request.name or f"Scheduled {request.action_name}",
        action_name=request.action_name,
        parameters=request.parameters,
        schedule_type=request.schedule_type,
        schedule_config=request.schedule_config,
        condition_expression=request.condition_expression,
        created_by="api_user",
        status="active",
        enabled=True,
    )

    # Parse condition if provided
    if request.schedule_type == "conditional" and request.condition_expression:
        # Basic parsing: "cpu > 95% for 10m"
        # TODO: Implement proper condition parser
        pass

    db.add(scheduled)
    db.commit()
    db.refresh(scheduled)

    logger.info(
        "scheduled_action_created",
        job_id=job_id,
        action_name=request.action_name,
        schedule_type=request.schedule_type,
    )

    return {
        "status": "created",
        "job_id": job_id,
        "scheduled_action_id": scheduled.id,
    }


@router.get("/scheduled/{job_id}")
async def get_scheduled_action(job_id: str, db: Session = Depends(get_db)):
    """Get details of a scheduled action."""
    scheduled = db.query(ScheduledAction).filter(ScheduledAction.job_id == job_id).first()
    if not scheduled:
        raise HTTPException(status_code=404, detail="Scheduled action not found")

    return {
        "id": scheduled.id,
        "job_id": scheduled.job_id,
        "name": scheduled.name,
        "action_name": scheduled.action_name,
        "parameters": scheduled.parameters,
        "schedule_type": scheduled.schedule_type,
        "schedule_config": scheduled.schedule_config,
        "condition_expression": scheduled.condition_expression,
        "condition_metric": scheduled.condition_metric,
        "condition_operator": scheduled.condition_operator,
        "condition_threshold": scheduled.condition_threshold,
        "condition_duration_seconds": scheduled.condition_duration_seconds,
        "status": scheduled.status,
        "enabled": scheduled.enabled,
        "next_run": scheduled.next_run.isoformat() if scheduled.next_run else None,
        "last_run": scheduled.last_run.isoformat() if scheduled.last_run else None,
        "last_result": scheduled.last_result,
        "run_count": scheduled.run_count,
        "error_count": scheduled.error_count,
        "max_runs": scheduled.max_runs,
        "expires_at": scheduled.expires_at.isoformat() if scheduled.expires_at else None,
        "created_by": scheduled.created_by,
        "created_at": scheduled.created_at.isoformat() if scheduled.created_at else None,
    }


@router.post("/scheduled/{job_id}/pause")
async def pause_scheduled_action(job_id: str, db: Session = Depends(get_db)):
    """Pause a scheduled action."""
    scheduled = db.query(ScheduledAction).filter(ScheduledAction.job_id == job_id).first()
    if not scheduled:
        raise HTTPException(status_code=404, detail="Scheduled action not found")

    scheduled.status = "paused"
    scheduled.enabled = False
    db.commit()

    logger.info("scheduled_action_paused", job_id=job_id)

    return {"status": "paused", "job_id": job_id}


@router.post("/scheduled/{job_id}/resume")
async def resume_scheduled_action(job_id: str, db: Session = Depends(get_db)):
    """Resume a paused scheduled action."""
    scheduled = db.query(ScheduledAction).filter(ScheduledAction.job_id == job_id).first()
    if not scheduled:
        raise HTTPException(status_code=404, detail="Scheduled action not found")

    scheduled.status = "active"
    scheduled.enabled = True
    db.commit()

    logger.info("scheduled_action_resumed", job_id=job_id)

    return {"status": "active", "job_id": job_id}


@router.delete("/scheduled/{job_id}")
async def delete_scheduled_action(job_id: str, db: Session = Depends(get_db)):
    """Delete a scheduled action."""
    scheduled = db.query(ScheduledAction).filter(ScheduledAction.job_id == job_id).first()
    if not scheduled:
        raise HTTPException(status_code=404, detail="Scheduled action not found")

    db.delete(scheduled)
    db.commit()

    logger.info("scheduled_action_deleted", job_id=job_id)

    return {"status": "deleted", "job_id": job_id}
