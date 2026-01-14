"""
LLM Usage Tracking Service.

Tracks token usage and costs for all LLM API calls across the application.
"""

from datetime import datetime, timedelta
from typing import Any, Optional

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import LlmUsageLog, LlmUsageStats

logger = structlog.get_logger()


# OpenAI pricing per 1M tokens (as of January 2025)
# Prices in USD
OPENAI_PRICING = {
    # GPT-4o models
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-11-20": {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-08-06": {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-05-13": {"input": 5.00, "output": 15.00},
    # GPT-4o mini
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o-mini-2024-07-18": {"input": 0.15, "output": 0.60},
    # GPT-4 Turbo
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4-turbo-2024-04-09": {"input": 10.00, "output": 30.00},
    "gpt-4-turbo-preview": {"input": 10.00, "output": 30.00},
    # GPT-4
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-4-0613": {"input": 30.00, "output": 60.00},
    # GPT-3.5 Turbo
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "gpt-3.5-turbo-0125": {"input": 0.50, "output": 1.50},
    # Embedding models (output price is 0)
    "text-embedding-3-small": {"input": 0.02, "output": 0},
    "text-embedding-3-large": {"input": 0.13, "output": 0},
    "text-embedding-ada-002": {"input": 0.10, "output": 0},
}

# Default pricing for unknown models
DEFAULT_PRICING = {"input": 1.00, "output": 2.00}


class LlmUsageService:
    """Service for tracking and reporting LLM usage."""

    def __init__(self, db: Session = None):
        self._db = db

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def calculate_cost_cents(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculate cost in cents for a request.

        Args:
            model: Model name (e.g., 'gpt-4o-mini')
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens

        Returns:
            Cost in cents (float for precision with cheap models/embeddings)
        """
        pricing = OPENAI_PRICING.get(model, DEFAULT_PRICING)

        # Price per 1M tokens, so divide by 1,000,000
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]

        # Convert to cents (keep as float for precision)
        total_cents = (input_cost + output_cost) * 100
        return total_cents

    def log_usage(
        self,
        feature: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        function_name: Optional[str] = None,
        context: Optional[str] = None,
        session_id: Optional[str] = None,
        tool_calls_count: int = 0,
        cached: bool = False,
    ) -> LlmUsageLog:
        """
        Log a single LLM API request.

        Args:
            feature: Feature area (chat, journal, dns, work, settings)
            model: Model name
            prompt_tokens: Input tokens
            completion_tokens: Output tokens
            function_name: Specific function (e.g., 'chat_stream', 'fact_extraction')
            context: Chat context (e.g., 'general', 'monitoring')
            session_id: Session ID for chat requests
            tool_calls_count: Number of tool calls made
            cached: Whether response was cached

        Returns:
            Created LlmUsageLog record
        """
        cost_cents = self.calculate_cost_cents(model, prompt_tokens, completion_tokens)
        total_tokens = prompt_tokens + completion_tokens

        log_entry = LlmUsageLog(
            timestamp=datetime.utcnow(),
            feature=feature,
            function_name=function_name,
            context=context,
            session_id=session_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_cents=cost_cents,
            tool_calls_count=tool_calls_count,
            cached=cached,
        )

        self.db.add(log_entry)
        self.db.commit()

        logger.info(
            "llm_usage_logged",
            feature=feature,
            model=model,
            total_tokens=total_tokens,
            cost_cents=cost_cents,
        )

        return log_entry

    def get_usage_summary(self, hours: int = 24) -> dict[str, Any]:
        """
        Get aggregated usage summary for dashboard.

        Args:
            hours: Number of hours to look back

        Returns:
            Summary dict with totals and breakdowns
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Get totals
        totals = (
            self.db.query(
                func.count(LlmUsageLog.id).label("request_count"),
                func.sum(LlmUsageLog.prompt_tokens).label("prompt_tokens"),
                func.sum(LlmUsageLog.completion_tokens).label("completion_tokens"),
                func.sum(LlmUsageLog.total_tokens).label("total_tokens"),
                func.sum(LlmUsageLog.cost_cents).label("total_cost_cents"),
            )
            .filter(LlmUsageLog.timestamp >= cutoff)
            .first()
        )

        # Get breakdown by feature
        by_feature = (
            self.db.query(
                LlmUsageLog.feature,
                func.count(LlmUsageLog.id).label("request_count"),
                func.sum(LlmUsageLog.total_tokens).label("total_tokens"),
                func.sum(LlmUsageLog.cost_cents).label("cost_cents"),
            )
            .filter(LlmUsageLog.timestamp >= cutoff)
            .group_by(LlmUsageLog.feature)
            .all()
        )

        # Get breakdown by model
        by_model = (
            self.db.query(
                LlmUsageLog.model,
                func.count(LlmUsageLog.id).label("request_count"),
                func.sum(LlmUsageLog.total_tokens).label("total_tokens"),
                func.sum(LlmUsageLog.cost_cents).label("cost_cents"),
            )
            .filter(LlmUsageLog.timestamp >= cutoff)
            .group_by(LlmUsageLog.model)
            .all()
        )

        return {
            "period_hours": hours,
            "request_count": totals.request_count or 0,
            "prompt_tokens": totals.prompt_tokens or 0,
            "completion_tokens": totals.completion_tokens or 0,
            "total_tokens": totals.total_tokens or 0,
            "total_cost_cents": totals.total_cost_cents or 0,
            "total_cost_dollars": (totals.total_cost_cents or 0) / 100,
            "by_feature": [
                {
                    "feature": row.feature,
                    "request_count": row.request_count,
                    "total_tokens": row.total_tokens or 0,
                    "cost_cents": row.cost_cents or 0,
                }
                for row in by_feature
            ],
            "by_model": [
                {
                    "model": row.model,
                    "request_count": row.request_count,
                    "total_tokens": row.total_tokens or 0,
                    "cost_cents": row.cost_cents or 0,
                }
                for row in by_model
            ],
        }

    def get_usage_history(self, hours: int = 168) -> list[dict[str, Any]]:
        """
        Get hourly usage data for charts.

        Args:
            hours: Number of hours to look back (default 7 days)

        Returns:
            List of hourly data points
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Group by hour
        hourly_data = (
            self.db.query(
                func.date_trunc("hour", LlmUsageLog.timestamp).label("hour"),
                func.count(LlmUsageLog.id).label("request_count"),
                func.sum(LlmUsageLog.total_tokens).label("total_tokens"),
                func.sum(LlmUsageLog.cost_cents).label("cost_cents"),
            )
            .filter(LlmUsageLog.timestamp >= cutoff)
            .group_by(func.date_trunc("hour", LlmUsageLog.timestamp))
            .order_by(func.date_trunc("hour", LlmUsageLog.timestamp))
            .all()
        )

        return [
            {
                "timestamp": row.hour.isoformat() if row.hour else None,
                "request_count": row.request_count,
                "total_tokens": row.total_tokens or 0,
                "cost_cents": row.cost_cents or 0,
            }
            for row in hourly_data
        ]

    def get_usage_by_feature(self, hours: int = 24) -> list[dict[str, Any]]:
        """
        Get detailed breakdown by feature and function.

        Args:
            hours: Number of hours to look back

        Returns:
            List of feature/function breakdowns
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        breakdown = (
            self.db.query(
                LlmUsageLog.feature,
                LlmUsageLog.function_name,
                LlmUsageLog.model,
                func.count(LlmUsageLog.id).label("request_count"),
                func.sum(LlmUsageLog.prompt_tokens).label("prompt_tokens"),
                func.sum(LlmUsageLog.completion_tokens).label("completion_tokens"),
                func.sum(LlmUsageLog.total_tokens).label("total_tokens"),
                func.sum(LlmUsageLog.cost_cents).label("cost_cents"),
                func.avg(LlmUsageLog.total_tokens).label("avg_tokens"),
            )
            .filter(LlmUsageLog.timestamp >= cutoff)
            .group_by(
                LlmUsageLog.feature,
                LlmUsageLog.function_name,
                LlmUsageLog.model,
            )
            .order_by(func.sum(LlmUsageLog.cost_cents).desc())
            .all()
        )

        return [
            {
                "feature": row.feature,
                "function_name": row.function_name,
                "model": row.model,
                "request_count": row.request_count,
                "prompt_tokens": row.prompt_tokens or 0,
                "completion_tokens": row.completion_tokens or 0,
                "total_tokens": row.total_tokens or 0,
                "cost_cents": row.cost_cents or 0,
                "avg_tokens_per_request": int(row.avg_tokens or 0),
            }
            for row in breakdown
        ]

    def get_daily_history(self, days: int = 30) -> list[dict[str, Any]]:
        """
        Get daily usage data for longer time periods.

        Args:
            days: Number of days to look back (default 30)

        Returns:
            List of daily data points
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Group by day
        daily_data = (
            self.db.query(
                func.date_trunc("day", LlmUsageLog.timestamp).label("day"),
                func.count(LlmUsageLog.id).label("request_count"),
                func.sum(LlmUsageLog.total_tokens).label("total_tokens"),
                func.sum(LlmUsageLog.prompt_tokens).label("prompt_tokens"),
                func.sum(LlmUsageLog.completion_tokens).label("completion_tokens"),
                func.sum(LlmUsageLog.cost_cents).label("cost_cents"),
            )
            .filter(LlmUsageLog.timestamp >= cutoff)
            .group_by(func.date_trunc("day", LlmUsageLog.timestamp))
            .order_by(func.date_trunc("day", LlmUsageLog.timestamp))
            .all()
        )

        return [
            {
                "date": row.day.strftime("%Y-%m-%d") if row.day else None,
                "request_count": row.request_count,
                "total_tokens": row.total_tokens or 0,
                "prompt_tokens": row.prompt_tokens or 0,
                "completion_tokens": row.completion_tokens or 0,
                "cost_cents": row.cost_cents or 0,
            }
            for row in daily_data
        ]

    def get_monthly_history(self, months: int = 12) -> list[dict[str, Any]]:
        """
        Get monthly usage data for year/month historical view.

        Args:
            months: Number of months to look back (default 12)

        Returns:
            List of monthly data points with year/month breakdown
        """
        cutoff = datetime.utcnow() - timedelta(days=months * 31)  # Approximate

        # Group by month
        monthly_data = (
            self.db.query(
                func.date_trunc("month", LlmUsageLog.timestamp).label("month"),
                func.count(LlmUsageLog.id).label("request_count"),
                func.sum(LlmUsageLog.total_tokens).label("total_tokens"),
                func.sum(LlmUsageLog.prompt_tokens).label("prompt_tokens"),
                func.sum(LlmUsageLog.completion_tokens).label("completion_tokens"),
                func.sum(LlmUsageLog.cost_cents).label("cost_cents"),
            )
            .filter(LlmUsageLog.timestamp >= cutoff)
            .group_by(func.date_trunc("month", LlmUsageLog.timestamp))
            .order_by(func.date_trunc("month", LlmUsageLog.timestamp))
            .all()
        )

        return [
            {
                "year": row.month.year if row.month else None,
                "month": row.month.month if row.month else None,
                "month_name": row.month.strftime("%B") if row.month else None,
                "year_month": row.month.strftime("%Y-%m") if row.month else None,
                "request_count": row.request_count,
                "total_tokens": row.total_tokens or 0,
                "prompt_tokens": row.prompt_tokens or 0,
                "completion_tokens": row.completion_tokens or 0,
                "cost_cents": row.cost_cents or 0,
            }
            for row in monthly_data
        ]

    def get_usage_trends(self, hours: int = 168) -> dict[str, Any]:
        """
        Get usage trends with period-over-period comparison.

        Args:
            hours: Number of hours for current period (default 7 days)

        Returns:
            Dict with current period, previous period, and percent changes
        """
        now = datetime.utcnow()
        current_start = now - timedelta(hours=hours)
        previous_start = current_start - timedelta(hours=hours)

        # Get current period stats
        current = self._get_period_totals(current_start, now)

        # Get previous period stats
        previous = self._get_period_totals(previous_start, current_start)

        # Calculate percent changes
        def calc_change(current_val: int, previous_val: int) -> float:
            if previous_val == 0:
                return 100.0 if current_val > 0 else 0.0
            return round(((current_val - previous_val) / previous_val) * 100, 1)

        return {
            "period_hours": hours,
            "current_period": {
                "start": current_start.isoformat(),
                "end": now.isoformat(),
                "request_count": current["request_count"],
                "total_tokens": current["total_tokens"],
                "cost_cents": current["cost_cents"],
                "cost_dollars": current["cost_cents"] / 100,
            },
            "previous_period": {
                "start": previous_start.isoformat(),
                "end": current_start.isoformat(),
                "request_count": previous["request_count"],
                "total_tokens": previous["total_tokens"],
                "cost_cents": previous["cost_cents"],
                "cost_dollars": previous["cost_cents"] / 100,
            },
            "percent_change": {
                "request_count": calc_change(current["request_count"], previous["request_count"]),
                "total_tokens": calc_change(current["total_tokens"], previous["total_tokens"]),
                "cost": calc_change(current["cost_cents"], previous["cost_cents"]),
            },
        }

    def _get_period_totals(self, start: datetime, end: datetime) -> dict[str, int]:
        """Get totals for a specific time period."""
        totals = (
            self.db.query(
                func.count(LlmUsageLog.id).label("request_count"),
                func.sum(LlmUsageLog.total_tokens).label("total_tokens"),
                func.sum(LlmUsageLog.cost_cents).label("cost_cents"),
            )
            .filter(
                LlmUsageLog.timestamp >= start,
                LlmUsageLog.timestamp < end,
            )
            .first()
        )

        return {
            "request_count": totals.request_count or 0,
            "total_tokens": totals.total_tokens or 0,
            "cost_cents": totals.cost_cents or 0,
        }

    def aggregate_hourly_stats(self) -> int:
        """
        Aggregate usage logs into hourly stats.
        Should be called hourly by background task.

        Returns:
            Number of stats records created
        """
        # Get the last hour's boundary
        now = datetime.utcnow()
        hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        hour_end = hour_start + timedelta(hours=1)

        # Check if already aggregated
        existing = (
            self.db.query(LlmUsageStats)
            .filter(
                LlmUsageStats.timestamp == hour_start,
                LlmUsageStats.period == "hour",
            )
            .first()
        )

        if existing:
            logger.info("hourly_stats_already_aggregated", hour=hour_start.isoformat())
            return 0

        # Aggregate by feature and model
        aggregates = (
            self.db.query(
                LlmUsageLog.feature,
                LlmUsageLog.model,
                func.count(LlmUsageLog.id).label("request_count"),
                func.sum(LlmUsageLog.prompt_tokens).label("prompt_tokens"),
                func.sum(LlmUsageLog.completion_tokens).label("completion_tokens"),
                func.sum(LlmUsageLog.total_tokens).label("total_tokens"),
                func.sum(LlmUsageLog.cost_cents).label("cost_cents"),
            )
            .filter(
                LlmUsageLog.timestamp >= hour_start,
                LlmUsageLog.timestamp < hour_end,
            )
            .group_by(LlmUsageLog.feature, LlmUsageLog.model)
            .all()
        )

        count = 0
        for row in aggregates:
            stat = LlmUsageStats(
                timestamp=hour_start,
                period="hour",
                feature=row.feature,
                model=row.model,
                request_count=row.request_count,
                prompt_tokens=row.prompt_tokens or 0,
                completion_tokens=row.completion_tokens or 0,
                total_tokens=row.total_tokens or 0,
                total_cost_cents=row.cost_cents or 0,
            )
            self.db.add(stat)
            count += 1

        self.db.commit()
        logger.info("hourly_stats_aggregated", hour=hour_start.isoformat(), records=count)
        return count


# Singleton instance
_usage_service: Optional[LlmUsageService] = None


def get_usage_service() -> LlmUsageService:
    """Get or create the singleton usage service."""
    global _usage_service
    if _usage_service is None:
        _usage_service = LlmUsageService()
    return _usage_service


def log_llm_usage(
    feature: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    **kwargs,
) -> None:
    """
    Convenience function to log LLM usage.

    This is a fire-and-forget function that logs usage without blocking.
    """
    try:
        service = get_usage_service()
        service.log_usage(
            feature=feature,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            **kwargs,
        )
    except Exception as e:
        logger.error("llm_usage_log_error", error=str(e))
