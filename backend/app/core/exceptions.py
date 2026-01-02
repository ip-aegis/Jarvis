"""Custom exception classes for Jarvis application."""

from typing import Any, Optional


class JarvisException(Exception):
    """Base exception for Jarvis application."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(JarvisException):
    """Resource not found error."""

    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            code="NOT_FOUND",
            status_code=404,
            details={"resource": resource, "identifier": str(identifier)},
        )


class ValidationError(JarvisException):
    """Input validation error."""

    def __init__(self, field: str, message: str):
        super().__init__(
            message=f"Validation error on {field}: {message}",
            code="VALIDATION_ERROR",
            status_code=422,
            details={"field": field},
        )


class ExternalServiceError(JarvisException):
    """Base class for external service errors."""

    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"External service error ({service}): {message}",
            code="EXTERNAL_SERVICE_ERROR",
            status_code=502,
            details={"service": service},
        )


class SSHConnectionError(ExternalServiceError):
    """SSH connection or command execution error."""

    def __init__(self, host: str, message: str):
        super().__init__(service="SSH", message=message)
        self.details["host"] = host
        self.code = "SSH_CONNECTION_ERROR"


class OllamaServiceError(ExternalServiceError):
    """Ollama LLM service error."""

    def __init__(self, message: str):
        super().__init__(service="Ollama", message=message)
        self.code = "OLLAMA_SERVICE_ERROR"


class SearchServiceError(ExternalServiceError):
    """SearXNG search service error."""

    def __init__(self, message: str):
        super().__init__(service="SearXNG", message=message)
        self.code = "SEARCH_SERVICE_ERROR"


class AuthenticationError(JarvisException):
    """Authentication required or failed."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=401,
        )


class AuthorizationError(JarvisException):
    """Permission denied error."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=403,
        )


class RateLimitError(JarvisException):
    """Rate limit exceeded error."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            code="RATE_LIMIT_ERROR",
            status_code=429,
        )
