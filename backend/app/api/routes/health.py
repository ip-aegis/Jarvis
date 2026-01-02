"""Health check endpoints for monitoring service status."""

import asyncio
import time
from enum import Enum
from typing import Dict, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.ollama import OllamaService
from app.services.search import SearchService

router = APIRouter(tags=["health"])


class HealthStatus(str, Enum):
    """Health status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class DependencyHealth(BaseModel):
    """Health status of a single dependency."""
    status: HealthStatus
    latency_ms: Optional[float] = None
    message: Optional[str] = None


class HealthResponse(BaseModel):
    """Full health check response."""
    status: HealthStatus
    version: str
    dependencies: Dict[str, DependencyHealth]


async def check_database(db: Session) -> DependencyHealth:
    """Check database connectivity."""
    try:
        start = time.perf_counter()
        db.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start) * 1000
        return DependencyHealth(
            status=HealthStatus.HEALTHY,
            latency_ms=round(latency, 2),
        )
    except Exception as e:
        return DependencyHealth(
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )


async def check_ollama() -> DependencyHealth:
    """Check Ollama LLM service connectivity."""
    try:
        start = time.perf_counter()
        ollama = OllamaService()
        is_healthy = await ollama.health_check()
        latency = (time.perf_counter() - start) * 1000

        if is_healthy:
            return DependencyHealth(
                status=HealthStatus.HEALTHY,
                latency_ms=round(latency, 2),
            )
        return DependencyHealth(
            status=HealthStatus.UNHEALTHY,
            message="Ollama not responding",
        )
    except Exception as e:
        return DependencyHealth(
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )


async def check_searxng() -> DependencyHealth:
    """Check SearXNG search service connectivity."""
    try:
        start = time.perf_counter()
        search = SearchService()
        is_healthy = await search.health_check()
        latency = (time.perf_counter() - start) * 1000

        if is_healthy:
            return DependencyHealth(
                status=HealthStatus.HEALTHY,
                latency_ms=round(latency, 2),
            )
        # Search is optional - degraded not unhealthy
        return DependencyHealth(
            status=HealthStatus.DEGRADED,
            message="SearXNG not responding",
        )
    except Exception as e:
        return DependencyHealth(
            status=HealthStatus.DEGRADED,
            message=str(e),
        )


@router.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """
    Comprehensive health check with dependency status.

    Returns status of all critical dependencies:
    - database: PostgreSQL/TimescaleDB connection
    - ollama: LLM service for chat functionality
    - searxng: Web search service (optional)
    """
    # Run all checks concurrently
    db_health, ollama_health, searxng_health = await asyncio.gather(
        check_database(db),
        check_ollama(),
        check_searxng(),
    )

    dependencies = {
        "database": db_health,
        "ollama": ollama_health,
        "searxng": searxng_health,
    }

    # Determine overall status
    statuses = [d.status for d in dependencies.values()]

    if HealthStatus.UNHEALTHY in statuses:
        # Database unhealthy = overall unhealthy
        if dependencies["database"].status == HealthStatus.UNHEALTHY:
            overall = HealthStatus.UNHEALTHY
        # Ollama unhealthy = degraded (can still do other things)
        elif dependencies["ollama"].status == HealthStatus.UNHEALTHY:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.DEGRADED
    elif HealthStatus.DEGRADED in statuses:
        overall = HealthStatus.DEGRADED
    else:
        overall = HealthStatus.HEALTHY

    return HealthResponse(
        status=overall,
        version="0.1.0",
        dependencies=dependencies,
    )


@router.get("/health/live")
async def liveness():
    """
    Kubernetes liveness probe - is the application running?

    This endpoint always returns 200 if the app is responding.
    Used to detect if the application has crashed and needs restart.
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(db: Session = Depends(get_db)):
    """
    Kubernetes readiness probe - can the app handle traffic?

    Returns 200 if the application can handle requests (database connected).
    Returns 503 if the application cannot handle requests.
    """
    db_health = await check_database(db)

    if db_health.status == HealthStatus.UNHEALTHY:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": db_health.message},
        )

    return {"status": "ready"}
