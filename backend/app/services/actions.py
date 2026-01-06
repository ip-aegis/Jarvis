"""
Action execution service with confirmation, audit logging, and scheduling support.
"""
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import ActionAudit, PendingConfirmation
from app.tools.base import ActionCategory, ActionType

logger = get_logger(__name__)


@dataclass
class ActionResult:
    """Result of an action execution."""

    success: bool
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    action_id: Optional[str] = None
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None
    affected_resources: Optional[list[str]] = None


@dataclass
class ActionDefinition:
    """
    Definition of an executable action.
    Used to register actions with the ActionService.
    """

    name: str
    description: str
    handler: Callable
    action_type: ActionType = ActionType.READ
    category: ActionCategory = ActionCategory.SYSTEM
    requires_confirmation: bool = False
    confirmation_message: Optional[str] = None
    rollback_handler: Optional[Callable] = None
    target_type: Optional[str] = None  # 'server', 'network_device', 'service'

    def get_confirmation_prompt(self, parameters: dict[str, Any]) -> str:
        """Generate confirmation prompt with parameters filled in."""
        if self.confirmation_message:
            try:
                return self.confirmation_message.format(**parameters)
            except KeyError:
                return self.confirmation_message
        return f"Confirm execution of {self.name}?"


class ActionRegistry:
    """Registry of available actions."""

    def __init__(self):
        self._actions: dict[str, ActionDefinition] = {}

    def register(self, action: ActionDefinition):
        """Register an action definition."""
        self._actions[action.name] = action
        logger.debug("action_registered", action_name=action.name, action_type=action.action_type)

    def get(self, name: str) -> Optional[ActionDefinition]:
        """Get an action definition by name."""
        return self._actions.get(name)

    def list_actions(self, category: Optional[ActionCategory] = None) -> list[ActionDefinition]:
        """List all registered actions, optionally filtered by category."""
        actions = list(self._actions.values())
        if category:
            actions = [a for a in actions if a.category == category]
        return actions


# Global action registry
action_registry = ActionRegistry()


class ActionService:
    """
    Manages action execution lifecycle including:
    - Audit logging
    - Confirmation flow for destructive actions
    - Action execution with error handling
    - Rollback support
    """

    def __init__(self, confirmation_timeout_minutes: int = 5):
        self.confirmation_timeout = timedelta(minutes=confirmation_timeout_minutes)

    async def execute_action(
        self,
        action_name: str,
        parameters: dict[str, Any],
        user_id: str,
        session_id: str,
        natural_input: str,
        db: Session,
        skip_confirmation: bool = False,
        llm_interpretation: Optional[str] = None,
    ) -> ActionResult:
        """
        Execute an action with proper audit and confirmation flow.

        Args:
            action_name: Name of the registered action
            parameters: Parameters to pass to the action handler
            user_id: ID of the user initiating the action
            session_id: Chat session ID
            natural_input: Original natural language input
            db: Database session
            skip_confirmation: Skip confirmation (for scheduled actions)
            llm_interpretation: How LLM interpreted the request

        Returns:
            ActionResult with status and data
        """
        # Get action definition
        action = action_registry.get(action_name)
        if not action:
            return ActionResult(
                success=False,
                error=f"Unknown action: {action_name}",
            )

        # Create audit record
        action_id = uuid.uuid4()
        audit = ActionAudit(
            action_id=action_id,
            action_name=action_name,
            action_type=action.action_type.value,
            category=action.category.value,
            parameters=parameters,
            target_type=action.target_type,
            initiated_by=user_id,
            session_id=session_id,
            natural_language_input=natural_input,
            llm_interpretation=llm_interpretation,
            status="pending",
            confirmation_required=action.requires_confirmation and not skip_confirmation,
        )

        # Extract target info if available
        if "server_id" in parameters:
            audit.target_id = parameters["server_id"]
            audit.target_type = "server"
        elif "device_id" in parameters:
            audit.target_id = parameters["device_id"]
            audit.target_type = "network_device"

        db.add(audit)
        db.commit()

        logger.info(
            "action_initiated",
            action_id=str(action_id),
            action_name=action_name,
            action_type=action.action_type.value,
            user_id=user_id,
        )

        # Check if confirmation required
        if action.requires_confirmation and not skip_confirmation:
            return await self._request_confirmation(action, parameters, audit, db)

        # Execute immediately
        return await self._execute_with_audit(action, parameters, audit, db)

    async def _request_confirmation(
        self,
        action: ActionDefinition,
        parameters: dict[str, Any],
        audit: ActionAudit,
        db: Session,
    ) -> ActionResult:
        """Create a pending confirmation request."""

        confirmation_prompt = action.get_confirmation_prompt(parameters)
        risk_summary = self._generate_risk_summary(action, parameters)
        affected_resources = self._identify_affected_resources(action, parameters, db)

        confirmation = PendingConfirmation(
            action_id=audit.action_id,
            expires_at=datetime.utcnow() + self.confirmation_timeout,
            confirmation_prompt=confirmation_prompt,
            risk_summary=risk_summary,
            affected_resources=affected_resources,
        )
        db.add(confirmation)

        audit.status = "awaiting_confirmation"
        db.commit()

        logger.info(
            "confirmation_requested",
            action_id=str(audit.action_id),
            action_name=action.name,
            expires_at=confirmation.expires_at.isoformat(),
        )

        return ActionResult(
            success=True,
            action_id=str(audit.action_id),
            requires_confirmation=True,
            confirmation_prompt=confirmation_prompt,
            affected_resources=affected_resources,
            data={
                "status": "confirmation_required",
                "expires_at": confirmation.expires_at.isoformat(),
                "risk_summary": risk_summary,
            },
        )

    async def confirm_action(
        self,
        action_id: str,
        confirmed_by: str,
        db: Session,
    ) -> ActionResult:
        """Confirm and execute a pending action."""

        # Find pending confirmation
        try:
            action_uuid = uuid.UUID(action_id)
        except ValueError:
            return ActionResult(success=False, error="Invalid action ID format")

        confirmation = (
            db.query(PendingConfirmation)
            .filter(PendingConfirmation.action_id == action_uuid)
            .first()
        )

        if not confirmation:
            return ActionResult(success=False, error="Confirmation not found or already processed")

        if datetime.utcnow() > confirmation.expires_at:
            # Clean up expired confirmation
            audit = db.query(ActionAudit).filter(ActionAudit.action_id == action_uuid).first()
            if audit:
                audit.status = "expired"
            db.delete(confirmation)
            db.commit()
            return ActionResult(success=False, error="Confirmation expired")

        # Get audit and action
        audit = db.query(ActionAudit).filter(ActionAudit.action_id == action_uuid).first()
        if not audit:
            return ActionResult(success=False, error="Action audit record not found")

        action = action_registry.get(audit.action_name)
        if not action:
            return ActionResult(
                success=False, error=f"Action no longer registered: {audit.action_name}"
            )

        # Update audit
        audit.confirmed_by = confirmed_by
        audit.confirmed_at = datetime.utcnow()
        audit.status = "confirmed"

        # Delete confirmation record
        db.delete(confirmation)
        db.commit()

        logger.info(
            "action_confirmed",
            action_id=action_id,
            action_name=audit.action_name,
            confirmed_by=confirmed_by,
        )

        # Execute
        return await self._execute_with_audit(action, audit.parameters, audit, db)

    async def cancel_action(
        self,
        action_id: str,
        cancelled_by: str,
        db: Session,
    ) -> ActionResult:
        """Cancel a pending action."""

        try:
            action_uuid = uuid.UUID(action_id)
        except ValueError:
            return ActionResult(success=False, error="Invalid action ID format")

        confirmation = (
            db.query(PendingConfirmation)
            .filter(PendingConfirmation.action_id == action_uuid)
            .first()
        )

        if not confirmation:
            return ActionResult(success=False, error="Confirmation not found")

        audit = db.query(ActionAudit).filter(ActionAudit.action_id == action_uuid).first()
        if audit:
            audit.status = "cancelled"
            audit.completed_at = datetime.utcnow()

        db.delete(confirmation)
        db.commit()

        logger.info(
            "action_cancelled",
            action_id=action_id,
            cancelled_by=cancelled_by,
        )

        return ActionResult(
            success=True,
            action_id=action_id,
            data={"status": "cancelled"},
        )

    async def _execute_with_audit(
        self,
        action: ActionDefinition,
        parameters: dict[str, Any],
        audit: ActionAudit,
        db: Session,
    ) -> ActionResult:
        """Execute action and update audit trail."""

        audit.status = "executing"
        db.commit()

        try:
            # Execute the action handler
            result = await action.handler(**parameters)

            audit.status = "completed"
            audit.completed_at = datetime.utcnow()
            audit.result = result if isinstance(result, dict) else {"result": result}
            audit.rollback_available = action.rollback_handler is not None
            db.commit()

            logger.info(
                "action_completed",
                action_id=str(audit.action_id),
                action_name=action.name,
                action_type=action.action_type.value,
            )

            return ActionResult(
                success=True,
                action_id=str(audit.action_id),
                data=audit.result,
            )

        except Exception as e:
            audit.status = "failed"
            audit.completed_at = datetime.utcnow()
            audit.error_message = str(e)
            db.commit()

            logger.error(
                "action_failed",
                action_id=str(audit.action_id),
                action_name=action.name,
                error=str(e),
            )

            return ActionResult(
                success=False,
                action_id=str(audit.action_id),
                error=str(e),
            )

    async def rollback_action(
        self,
        action_id: str,
        rolled_back_by: str,
        db: Session,
    ) -> ActionResult:
        """Rollback a completed action if rollback is available."""

        try:
            action_uuid = uuid.UUID(action_id)
        except ValueError:
            return ActionResult(success=False, error="Invalid action ID format")

        audit = db.query(ActionAudit).filter(ActionAudit.action_id == action_uuid).first()
        if not audit:
            return ActionResult(success=False, error="Action not found")

        if not audit.rollback_available:
            return ActionResult(success=False, error="Rollback not available for this action")

        if audit.rollback_executed:
            return ActionResult(success=False, error="Rollback already executed")

        action = action_registry.get(audit.action_name)
        if not action or not action.rollback_handler:
            return ActionResult(success=False, error="Rollback handler not found")

        try:
            result = await action.rollback_handler(**audit.parameters)

            audit.rollback_executed = True
            audit.rollback_at = datetime.utcnow()
            audit.rollback_result = result if isinstance(result, dict) else {"result": result}
            db.commit()

            logger.info(
                "action_rolled_back",
                action_id=action_id,
                action_name=audit.action_name,
                rolled_back_by=rolled_back_by,
            )

            return ActionResult(
                success=True,
                action_id=action_id,
                data={"status": "rolled_back", "result": audit.rollback_result},
            )

        except Exception as e:
            logger.error(
                "rollback_failed",
                action_id=action_id,
                error=str(e),
            )
            return ActionResult(success=False, error=f"Rollback failed: {str(e)}")

    def _generate_risk_summary(
        self,
        action: ActionDefinition,
        parameters: dict[str, Any],
    ) -> str:
        """Generate a human-readable risk summary for an action."""

        if action.action_type == ActionType.DESTRUCTIVE:
            return f"This is a DESTRUCTIVE action that may cause downtime or data loss. Action: {action.name}"
        elif action.action_type == ActionType.WRITE:
            return f"This action will modify system state. Action: {action.name}"
        else:
            return f"This is a read-only action. Action: {action.name}"

    def _identify_affected_resources(
        self,
        action: ActionDefinition,
        parameters: dict[str, Any],
        db: Session,
    ) -> list[str]:
        """Identify resources that will be affected by this action."""

        resources = []

        if "server_id" in parameters:
            from app.models import Server

            server = db.query(Server).filter(Server.id == parameters["server_id"]).first()
            if server:
                resources.append(f"Server: {server.hostname} ({server.ip_address})")

        if "device_id" in parameters:
            from app.models import NetworkDevice

            device = (
                db.query(NetworkDevice).filter(NetworkDevice.id == parameters["device_id"]).first()
            )
            if device:
                resources.append(f"Network Device: {device.name} ({device.ip_address})")

        if "service_name" in parameters:
            resources.append(f"Service: {parameters['service_name']}")

        if "ip_to_block" in parameters:
            resources.append(f"IP Address: {parameters['ip_to_block']}")

        return resources

    async def get_audit_log(
        self,
        db: Session,
        limit: int = 50,
        action_type: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get action audit log with optional filters."""

        query = db.query(ActionAudit).order_by(ActionAudit.initiated_at.desc())

        if action_type:
            query = query.filter(ActionAudit.action_type == action_type)
        if status:
            query = query.filter(ActionAudit.status == status)
        if category:
            query = query.filter(ActionAudit.category == category)

        audits = query.limit(limit).all()

        return [
            {
                "action_id": str(a.action_id),
                "action_name": a.action_name,
                "action_type": a.action_type,
                "category": a.category,
                "status": a.status,
                "initiated_by": a.initiated_by,
                "initiated_at": a.initiated_at.isoformat() if a.initiated_at else None,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                "natural_language_input": a.natural_language_input,
                "target_type": a.target_type,
                "target_name": a.target_name,
                "result": a.result,
                "error_message": a.error_message,
                "rollback_available": a.rollback_available,
                "rollback_executed": a.rollback_executed,
            }
            for a in audits
        ]

    async def get_pending_confirmations(self, db: Session) -> list[dict[str, Any]]:
        """Get all pending action confirmations."""

        confirmations = (
            db.query(PendingConfirmation)
            .filter(PendingConfirmation.expires_at > datetime.utcnow())
            .all()
        )

        return [
            {
                "action_id": str(c.action_id),
                "confirmation_prompt": c.confirmation_prompt,
                "risk_summary": c.risk_summary,
                "affected_resources": c.affected_resources,
                "expires_at": c.expires_at.isoformat(),
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in confirmations
        ]

    async def cleanup_expired_confirmations(self, db: Session) -> int:
        """Clean up expired confirmation requests. Returns count of cleaned records."""

        expired = (
            db.query(PendingConfirmation)
            .filter(PendingConfirmation.expires_at <= datetime.utcnow())
            .all()
        )

        count = 0
        for confirmation in expired:
            audit = (
                db.query(ActionAudit)
                .filter(ActionAudit.action_id == confirmation.action_id)
                .first()
            )
            if audit:
                audit.status = "expired"
            db.delete(confirmation)
            count += 1

        db.commit()
        return count
