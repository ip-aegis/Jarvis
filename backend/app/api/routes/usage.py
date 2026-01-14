"""
LLM Usage Tracking API Routes.

Provides endpoints for viewing token usage and costs.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.llm_usage import LlmUsageService

router = APIRouter(prefix="/usage", tags=["usage"])


# =============================================================================
# Response Models
# =============================================================================


class FeatureUsage(BaseModel):
    feature: str
    request_count: int
    total_tokens: int
    cost_cents: float


class ModelUsage(BaseModel):
    model: str
    request_count: int
    total_tokens: int
    cost_cents: float


class UsageSummaryResponse(BaseModel):
    period_hours: int
    request_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    total_cost_cents: float
    total_cost_dollars: float
    by_feature: list[FeatureUsage]
    by_model: list[ModelUsage]


class HourlyUsage(BaseModel):
    timestamp: Optional[str]
    request_count: int
    total_tokens: int
    cost_cents: float


class DetailedUsage(BaseModel):
    feature: str
    function_name: Optional[str]
    model: Optional[str]
    request_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_cents: float
    avg_tokens_per_request: int


class DailyUsage(BaseModel):
    date: Optional[str]
    request_count: int
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    cost_cents: float


class MonthlyUsage(BaseModel):
    year: Optional[int]
    month: Optional[int]
    month_name: Optional[str]
    year_month: Optional[str]
    request_count: int
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    cost_cents: float


class PeriodStats(BaseModel):
    start: str
    end: str
    request_count: int
    total_tokens: int
    cost_cents: float
    cost_dollars: float


class PercentChange(BaseModel):
    request_count: float
    total_tokens: float
    cost: float


class UsageTrendsResponse(BaseModel):
    period_hours: int
    current_period: PeriodStats
    previous_period: PeriodStats
    percent_change: PercentChange


# =============================================================================
# Routes
# =============================================================================


@router.get("/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    hours: int = Query(24, ge=1, le=720, description="Hours to look back"),
    db: Session = Depends(get_db),
):
    """
    Get aggregated usage summary.

    Returns total tokens, costs, and breakdowns by feature and model.
    """
    service = LlmUsageService(db)
    summary = service.get_usage_summary(hours=hours)

    return UsageSummaryResponse(
        period_hours=summary["period_hours"],
        request_count=summary["request_count"],
        prompt_tokens=summary["prompt_tokens"],
        completion_tokens=summary["completion_tokens"],
        total_tokens=summary["total_tokens"],
        total_cost_cents=summary["total_cost_cents"],
        total_cost_dollars=summary["total_cost_dollars"],
        by_feature=[FeatureUsage(**f) for f in summary["by_feature"]],
        by_model=[ModelUsage(**m) for m in summary["by_model"]],
    )


@router.get("/history", response_model=list[HourlyUsage])
async def get_usage_history(
    hours: int = Query(168, ge=1, le=720, description="Hours to look back (default 7 days)"),
    db: Session = Depends(get_db),
):
    """
    Get hourly usage data for charts.

    Returns usage data points aggregated by hour.
    """
    service = LlmUsageService(db)
    history = service.get_usage_history(hours=hours)

    return [HourlyUsage(**h) for h in history]


@router.get("/by-feature", response_model=list[DetailedUsage])
async def get_usage_by_feature(
    hours: int = Query(24, ge=1, le=720, description="Hours to look back"),
    db: Session = Depends(get_db),
):
    """
    Get detailed usage breakdown by feature and function.

    Returns usage data grouped by feature, function name, and model.
    """
    service = LlmUsageService(db)
    breakdown = service.get_usage_by_feature(hours=hours)

    return [DetailedUsage(**d) for d in breakdown]


@router.post("/aggregate")
async def trigger_aggregation(
    db: Session = Depends(get_db),
):
    """
    Manually trigger hourly aggregation.

    This is normally run automatically but can be triggered manually.
    """
    service = LlmUsageService(db)
    count = service.aggregate_hourly_stats()

    return {"message": "Aggregation complete", "records_created": count}


@router.get("/daily-history", response_model=list[DailyUsage])
async def get_daily_history(
    days: int = Query(30, ge=1, le=365, description="Days to look back (default 30)"),
    db: Session = Depends(get_db),
):
    """
    Get daily usage data for monthly/yearly views.

    Returns usage data points aggregated by day for longer time periods.
    """
    service = LlmUsageService(db)
    history = service.get_daily_history(days=days)

    return [DailyUsage(**h) for h in history]


@router.get("/monthly-history", response_model=list[MonthlyUsage])
async def get_monthly_history(
    months: int = Query(12, ge=1, le=36, description="Months to look back (default 12)"),
    db: Session = Depends(get_db),
):
    """
    Get monthly usage data for year/month historical views.

    Returns usage data points aggregated by month for long-term tracking.
    """
    service = LlmUsageService(db)
    history = service.get_monthly_history(months=months)

    return [MonthlyUsage(**h) for h in history]


@router.get("/trends", response_model=UsageTrendsResponse)
async def get_usage_trends(
    hours: int = Query(
        168, ge=24, le=720, description="Hours for comparison period (default 7 days)"
    ),
    db: Session = Depends(get_db),
):
    """
    Get usage trends with period-over-period comparison.

    Compares current period with the previous period of the same length
    and returns percent changes for cost, tokens, and requests.
    """
    service = LlmUsageService(db)
    trends = service.get_usage_trends(hours=hours)

    return UsageTrendsResponse(
        period_hours=trends["period_hours"],
        current_period=PeriodStats(**trends["current_period"]),
        previous_period=PeriodStats(**trends["previous_period"]),
        percent_change=PercentChange(**trends["percent_change"]),
    )
