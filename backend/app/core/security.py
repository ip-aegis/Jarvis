"""Security utilities for JWT authentication."""

from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import get_settings
from app.core.exceptions import AuthenticationError

settings = get_settings()


class TokenData(BaseModel):
    """Data extracted from JWT token."""

    username: str
    exp: Optional[datetime] = None


class Token(BaseModel):
    """Token response model."""

    access_token: str
    token_type: str = "bearer"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token.

    Args:
        data: Data to encode in the token.
        expires_delta: Optional expiration time delta.

    Returns:
        Encoded JWT token string.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=settings.jwt_expire_hours))
    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> TokenData:
    """Decode and validate a JWT token.

    Args:
        token: The JWT token string.

    Returns:
        TokenData with extracted information.

    Raises:
        AuthenticationError: If token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        username: str = payload.get("sub")
        if username is None:
            raise AuthenticationError("Invalid token: missing subject")
        return TokenData(username=username)
    except JWTError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")


def authenticate_user(username: str, password: str) -> bool:
    """Authenticate user credentials against configured admin.

    Args:
        username: Username to authenticate.
        password: Password to verify.

    Returns:
        True if credentials are valid, False otherwise.
    """
    if username != settings.admin_username:
        return False
    return verify_password(password, settings.admin_password_hash)
