"""Rate limiting configuration using SlowAPI."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse


def get_request_identifier(request: Request) -> str:
    """Get identifier for rate limiting.

    Uses IP address as the primary identifier.
    Could be extended to use user ID for authenticated requests.
    """
    return get_remote_address(request)


# Create limiter instance with default limits
limiter = Limiter(
    key_func=get_request_identifier,
    default_limits=["100/minute"],  # Default: 100 requests per minute
)


async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> JSONResponse:
    """Custom handler for rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMIT_ERROR",
                "message": f"Rate limit exceeded: {exc.detail}",
                "details": {
                    "retry_after": getattr(exc, "retry_after", None),
                },
            }
        },
    )


# Export for use in routes
# Usage in routes:
# @router.post("/endpoint")
# @limiter.limit("10/minute")
# async def endpoint(request: Request):
#     ...
