"""Middleware for request logging and tracing."""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs all HTTP requests with timing and context."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]

        # Clear and bind request context for structured logging
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )

        start_time = time.perf_counter()

        # Log request start (skip for health checks to reduce noise)
        if not request.url.path.startswith("/health"):
            logger.info("request_started")

        try:
            response = await call_next(request)
            process_time = time.perf_counter() - start_time

            # Log request completion
            if not request.url.path.startswith("/health"):
                logger.info(
                    "request_completed",
                    status_code=response.status_code,
                    duration_ms=round(process_time * 1000, 2),
                )

            # Add request ID header for tracing
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as e:
            process_time = time.perf_counter() - start_time
            logger.exception(
                "request_failed",
                duration_ms=round(process_time * 1000, 2),
                error=str(e),
            )
            raise
