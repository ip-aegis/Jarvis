"""API dependencies for dependency injection."""

from typing import Optional

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.exceptions import AuthenticationError
from app.core.security import decode_token, TokenData

# OAuth2 scheme for token extraction
# tokenUrl is the endpoint where tokens are obtained
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=False,  # Don't auto-raise, we handle it manually
)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
) -> TokenData:
    """Get the current authenticated user from JWT token.

    Args:
        token: JWT token from Authorization header.

    Returns:
        TokenData with user information.

    Raises:
        AuthenticationError: If not authenticated or token invalid.
    """
    if not token:
        raise AuthenticationError("Not authenticated")

    return decode_token(token)


async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[TokenData]:
    """Get current user if authenticated, None otherwise.

    Use this for endpoints that work with or without authentication.

    Args:
        token: JWT token from Authorization header.

    Returns:
        TokenData if authenticated, None otherwise.
    """
    if not token:
        return None

    try:
        return decode_token(token)
    except AuthenticationError:
        return None
