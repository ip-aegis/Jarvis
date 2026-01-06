"""Home automation engine for trigger-based automations."""

import asyncio
from collections.abc import Callable
from datetime import datetime, time
from enum import Enum
from typing import Any, Optional

import structlog
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import HomeAutomation, HomeDevice, HomeEvent

logger = structlog.get_logger(__name__)


class TriggerType(str, Enum):
    """Types of automation triggers."""

    TIME = "time"  # Specific time of day
    SCHEDULE = "schedule"  # Cron-like schedule
    EVENT = "event"  # Device event (ring, motion, cycle_complete)
    STATE = "state"  # Device state change
    SUNRISE = "sunrise"  # At sunrise (requires location)
    SUNSET = "sunset"  # At sunset (requires location)


class ConditionType(str, Enum):
    """Types of automation conditions."""

    DEVICE_STATE = "device_state"  # Check device state
    TIME_RANGE = "time_range"  # Within time window
    DAY_OF_WEEK = "day_of_week"  # Specific days
    VARIABLE = "variable"  # Custom variable check


class ActionType(str, Enum):
    """Types of automation actions."""

    DEVICE_ACTION = "device_action"  # Execute device action
    NOTIFICATION = "notification"  # Send notification
    DELAY = "delay"  # Wait before next action
    CONDITION = "condition"  # Conditional action


class AutomationEngine:
    """Engine for evaluating and executing home automations.

    Handles trigger evaluation, condition checking, and action execution
    for automation rules stored in the database.
    """

    def __init__(self):
        """Initialize the automation engine."""
        self._logger = logger.bind(component="automation_engine")
        self._running = False
        self._check_interval = 60  # Check automations every 60 seconds
        self._last_check: dict[int, datetime] = {}  # Track last trigger times
        self._event_handlers: dict[str, list[Callable]] = {}

    async def start(self):
        """Start the automation engine background task."""
        if self._running:
            return

        self._running = True
        self._logger.info("automation_engine_started")
        asyncio.create_task(self._run_loop())

    async def stop(self):
        """Stop the automation engine."""
        self._running = False
        self._logger.info("automation_engine_stopped")

    async def _run_loop(self):
        """Main loop for checking time-based triggers."""
        while self._running:
            try:
                await self._check_time_triggers()
            except Exception as e:
                self._logger.error("automation_check_failed", error=str(e))

            await asyncio.sleep(self._check_interval)

    async def _check_time_triggers(self):
        """Check all time-based automation triggers."""
        db = SessionLocal()
        try:
            now = datetime.now()
            current_time = now.time()

            # Get enabled automations with time triggers
            automations = (
                db.query(HomeAutomation)
                .filter(
                    HomeAutomation.enabled == True,
                    HomeAutomation.trigger_type.in_(
                        [
                            TriggerType.TIME.value,
                            TriggerType.SCHEDULE.value,
                        ]
                    ),
                )
                .all()
            )

            for automation in automations:
                try:
                    should_trigger = await self._evaluate_time_trigger(
                        automation, now, current_time
                    )

                    if should_trigger:
                        # Check cooldown
                        if not self._is_cooldown_expired(automation):
                            continue

                        # Check conditions
                        if await self._evaluate_conditions(automation, db):
                            await self._execute_actions(automation, db)
                            self._update_trigger_stats(automation, db)

                except Exception as e:
                    self._logger.error(
                        "automation_trigger_failed", automation_id=automation.id, error=str(e)
                    )

        finally:
            db.close()

    async def _evaluate_time_trigger(
        self, automation: HomeAutomation, now: datetime, current_time: time
    ) -> bool:
        """Evaluate if a time-based trigger should fire."""
        config = automation.trigger_config or {}
        trigger_type = automation.trigger_type

        if trigger_type == TriggerType.TIME.value:
            # Specific time trigger
            trigger_time_str = config.get("time")
            if not trigger_time_str:
                return False

            # Parse time (HH:MM format)
            try:
                hour, minute = map(int, trigger_time_str.split(":"))
                trigger_time = time(hour, minute)

                # Check if within the check interval
                trigger_dt = datetime.combine(now.date(), trigger_time)
                diff = abs((now - trigger_dt).total_seconds())

                return diff <= self._check_interval

            except (ValueError, TypeError):
                return False

        elif trigger_type == TriggerType.SCHEDULE.value:
            # Cron-like schedule
            # Simplified: check days and time
            days = config.get("days", [])  # 0=Monday, 6=Sunday
            trigger_time_str = config.get("time")

            if days and now.weekday() not in days:
                return False

            if trigger_time_str:
                try:
                    hour, minute = map(int, trigger_time_str.split(":"))
                    trigger_time = time(hour, minute)
                    trigger_dt = datetime.combine(now.date(), trigger_time)
                    diff = abs((now - trigger_dt).total_seconds())
                    return diff <= self._check_interval
                except (ValueError, TypeError):
                    return False

        return False

    def _is_cooldown_expired(self, automation: HomeAutomation) -> bool:
        """Check if automation cooldown has expired."""
        cooldown = automation.cooldown_seconds or 0
        if cooldown <= 0:
            return True

        last_triggered = automation.last_triggered
        if not last_triggered:
            return True

        elapsed = (datetime.utcnow() - last_triggered).total_seconds()
        return elapsed >= cooldown

    async def _evaluate_conditions(self, automation: HomeAutomation, db: Session) -> bool:
        """Evaluate all conditions for an automation."""
        conditions = automation.conditions or []

        if not conditions:
            return True

        for condition in conditions:
            condition_type = condition.get("type")
            config = condition.get("config", {})

            if condition_type == ConditionType.DEVICE_STATE.value:
                if not await self._check_device_state_condition(config, db):
                    return False

            elif condition_type == ConditionType.TIME_RANGE.value:
                if not self._check_time_range_condition(config):
                    return False

            elif condition_type == ConditionType.DAY_OF_WEEK.value:
                if not self._check_day_condition(config):
                    return False

        return True

    async def _check_device_state_condition(self, config: dict[str, Any], db: Session) -> bool:
        """Check device state condition."""
        device_id = config.get("device_id")
        attribute = config.get("attribute")
        operator = config.get("operator", "eq")
        value = config.get("value")

        if not all([device_id, attribute]):
            return False

        device = db.query(HomeDevice).filter_by(id=device_id).first()
        if not device:
            return False

        state = device.state or {}
        actual_value = state.get(attribute)

        if operator == "eq":
            return actual_value == value
        elif operator == "ne":
            return actual_value != value
        elif operator == "gt":
            return actual_value is not None and actual_value > value
        elif operator == "lt":
            return actual_value is not None and actual_value < value
        elif operator == "gte":
            return actual_value is not None and actual_value >= value
        elif operator == "lte":
            return actual_value is not None and actual_value <= value
        elif operator == "contains":
            return value in str(actual_value)
        elif operator == "is_true":
            return bool(actual_value)
        elif operator == "is_false":
            return not bool(actual_value)

        return False

    def _check_time_range_condition(self, config: dict[str, Any]) -> bool:
        """Check if current time is within a range."""
        start_str = config.get("start")
        end_str = config.get("end")

        if not start_str or not end_str:
            return True

        try:
            current = datetime.now().time()
            start_hour, start_min = map(int, start_str.split(":"))
            end_hour, end_min = map(int, end_str.split(":"))

            start_time = time(start_hour, start_min)
            end_time = time(end_hour, end_min)

            # Handle overnight ranges (e.g., 22:00 - 06:00)
            if start_time <= end_time:
                return start_time <= current <= end_time
            else:
                return current >= start_time or current <= end_time

        except (ValueError, TypeError):
            return True

    def _check_day_condition(self, config: dict[str, Any]) -> bool:
        """Check if current day matches condition."""
        days = config.get("days", [])
        if not days:
            return True

        return datetime.now().weekday() in days

    async def _execute_actions(self, automation: HomeAutomation, db: Session):
        """Execute all actions for an automation."""
        actions = automation.actions or []

        self._logger.info(
            "automation_executing",
            automation_id=automation.id,
            name=automation.name,
            action_count=len(actions),
        )

        for action in actions:
            try:
                action_type = action.get("type")
                config = action.get("config", {})

                if action_type == ActionType.DEVICE_ACTION.value:
                    await self._execute_device_action(config, db)

                elif action_type == ActionType.DELAY.value:
                    delay_seconds = config.get("seconds", 0)
                    if delay_seconds > 0:
                        await asyncio.sleep(min(delay_seconds, 300))  # Max 5 min

                elif action_type == ActionType.NOTIFICATION.value:
                    await self._send_notification(config)

            except Exception as e:
                self._logger.error(
                    "automation_action_failed",
                    automation_id=automation.id,
                    action_type=action.get("type"),
                    error=str(e),
                )

    async def _execute_device_action(self, config: dict[str, Any], db: Session):
        """Execute a device action."""
        from app.services.home import device_manager

        device_id = config.get("device_id")
        action = config.get("action")
        params = config.get("params", {})

        if not device_id or not action:
            return

        device = db.query(HomeDevice).filter_by(id=device_id).first()
        if not device:
            self._logger.warning("automation_device_not_found", device_id=device_id)
            return

        result = await device_manager.execute_action(
            device.platform, device.device_id, action, params
        )

        self._logger.info(
            "automation_device_action_executed",
            device_id=device_id,
            action=action,
            success=result.get("success", False),
        )

    async def _send_notification(self, config: dict[str, Any]):
        """Send a notification (placeholder for notification service)."""
        title = config.get("title", "Home Automation")
        message = config.get("message", "")
        priority = config.get("priority", "normal")

        self._logger.info(
            "automation_notification", title=title, message=message, priority=priority
        )

        # TODO: Integrate with notification service (push, email, etc.)

    def _update_trigger_stats(self, automation: HomeAutomation, db: Session):
        """Update automation trigger statistics."""
        automation.last_triggered = datetime.utcnow()
        automation.trigger_count = (automation.trigger_count or 0) + 1
        db.commit()

    # Event-based trigger handling

    async def handle_event(self, event: HomeEvent):
        """Handle a device event and check for matching automations."""
        db = SessionLocal()
        try:
            # Find automations triggered by this event type
            automations = (
                db.query(HomeAutomation)
                .filter(
                    HomeAutomation.enabled == True,
                    HomeAutomation.trigger_type == TriggerType.EVENT.value,
                )
                .all()
            )

            for automation in automations:
                config = automation.trigger_config or {}
                event_types = config.get("event_types", [])
                device_ids = config.get("device_ids", [])

                # Check if event matches trigger
                matches_type = not event_types or event.event_type in event_types
                matches_device = not device_ids or event.device_id in device_ids

                if matches_type and matches_device:
                    if not self._is_cooldown_expired(automation):
                        continue

                    if await self._evaluate_conditions(automation, db):
                        await self._execute_actions(automation, db)
                        self._update_trigger_stats(automation, db)

        finally:
            db.close()

    async def handle_state_change(
        self, device_id: int, old_state: dict[str, Any], new_state: dict[str, Any]
    ):
        """Handle a device state change and check for matching automations."""
        db = SessionLocal()
        try:
            # Find automations triggered by state changes
            automations = (
                db.query(HomeAutomation)
                .filter(
                    HomeAutomation.enabled == True,
                    HomeAutomation.trigger_type == TriggerType.STATE.value,
                )
                .all()
            )

            for automation in automations:
                config = automation.trigger_config or {}
                trigger_device_id = config.get("device_id")
                attribute = config.get("attribute")
                from_value = config.get("from")
                to_value = config.get("to")

                # Check if this state change matches
                if trigger_device_id and trigger_device_id != device_id:
                    continue

                if attribute:
                    old_val = old_state.get(attribute)
                    new_val = new_state.get(attribute)

                    if from_value is not None and old_val != from_value:
                        continue
                    if to_value is not None and new_val != to_value:
                        continue
                    if old_val == new_val:
                        continue  # No change

                if not self._is_cooldown_expired(automation):
                    continue

                if await self._evaluate_conditions(automation, db):
                    await self._execute_actions(automation, db)
                    self._update_trigger_stats(automation, db)

        finally:
            db.close()


class AutomationBuilder:
    """Helper class for building automation rules."""

    def __init__(self, name: str):
        """Initialize automation builder."""
        self.name = name
        self.trigger_type: Optional[str] = None
        self.trigger_config: dict[str, Any] = {}
        self.conditions: list[dict[str, Any]] = []
        self.actions: list[dict[str, Any]] = []
        self.cooldown_seconds = 0
        self.enabled = True

    def trigger_at_time(self, time_str: str) -> "AutomationBuilder":
        """Trigger at specific time (HH:MM)."""
        self.trigger_type = TriggerType.TIME.value
        self.trigger_config = {"time": time_str}
        return self

    def trigger_on_schedule(
        self, time_str: str, days: Optional[list[int]] = None
    ) -> "AutomationBuilder":
        """Trigger on schedule (days: 0=Monday, 6=Sunday)."""
        self.trigger_type = TriggerType.SCHEDULE.value
        self.trigger_config = {"time": time_str, "days": days or []}
        return self

    def trigger_on_event(
        self, event_types: list[str], device_ids: Optional[list[int]] = None
    ) -> "AutomationBuilder":
        """Trigger on device event."""
        self.trigger_type = TriggerType.EVENT.value
        self.trigger_config = {
            "event_types": event_types,
            "device_ids": device_ids or [],
        }
        return self

    def trigger_on_state_change(
        self, device_id: int, attribute: str, from_value: Any = None, to_value: Any = None
    ) -> "AutomationBuilder":
        """Trigger on device state change."""
        self.trigger_type = TriggerType.STATE.value
        self.trigger_config = {
            "device_id": device_id,
            "attribute": attribute,
            "from": from_value,
            "to": to_value,
        }
        return self

    def when_device_state(
        self, device_id: int, attribute: str, operator: str, value: Any
    ) -> "AutomationBuilder":
        """Add device state condition."""
        self.conditions.append(
            {
                "type": ConditionType.DEVICE_STATE.value,
                "config": {
                    "device_id": device_id,
                    "attribute": attribute,
                    "operator": operator,
                    "value": value,
                },
            }
        )
        return self

    def when_time_between(self, start: str, end: str) -> "AutomationBuilder":
        """Add time range condition."""
        self.conditions.append(
            {
                "type": ConditionType.TIME_RANGE.value,
                "config": {"start": start, "end": end},
            }
        )
        return self

    def when_day_is(self, days: list[int]) -> "AutomationBuilder":
        """Add day of week condition (0=Monday, 6=Sunday)."""
        self.conditions.append(
            {
                "type": ConditionType.DAY_OF_WEEK.value,
                "config": {"days": days},
            }
        )
        return self

    def then_device_action(
        self, device_id: int, action: str, params: Optional[dict[str, Any]] = None
    ) -> "AutomationBuilder":
        """Add device action."""
        self.actions.append(
            {
                "type": ActionType.DEVICE_ACTION.value,
                "config": {
                    "device_id": device_id,
                    "action": action,
                    "params": params or {},
                },
            }
        )
        return self

    def then_notify(
        self, title: str, message: str, priority: str = "normal"
    ) -> "AutomationBuilder":
        """Add notification action."""
        self.actions.append(
            {
                "type": ActionType.NOTIFICATION.value,
                "config": {
                    "title": title,
                    "message": message,
                    "priority": priority,
                },
            }
        )
        return self

    def then_delay(self, seconds: int) -> "AutomationBuilder":
        """Add delay between actions."""
        self.actions.append(
            {
                "type": ActionType.DELAY.value,
                "config": {"seconds": seconds},
            }
        )
        return self

    def with_cooldown(self, seconds: int) -> "AutomationBuilder":
        """Set cooldown between triggers."""
        self.cooldown_seconds = seconds
        return self

    def build(self) -> dict[str, Any]:
        """Build the automation configuration."""
        return {
            "name": self.name,
            "trigger_type": self.trigger_type,
            "trigger_config": self.trigger_config,
            "conditions": self.conditions,
            "actions": self.actions,
            "cooldown_seconds": self.cooldown_seconds,
            "enabled": self.enabled,
        }

    def save(self, db: Session) -> HomeAutomation:
        """Save automation to database."""
        config = self.build()
        automation = HomeAutomation(**config)
        db.add(automation)
        db.commit()
        db.refresh(automation)
        return automation


# Global automation engine instance
automation_engine = AutomationEngine()
