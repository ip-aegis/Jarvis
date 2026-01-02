"""Authentication endpoints."""

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.exceptions import AuthenticationError
from app.core.security import (
    authenticate_user,
    create_access_token,
    Token,
)
from app.api.deps import get_current_user, TokenData
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


class LoginRequest(BaseModel):
    """Login request body for JSON-based login."""
    username: str
    password: str


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> Token:
    """
    Authenticate user and return JWT token.

    Uses OAuth2 password flow (form data with username/password).

    Returns:
        Token with access_token and token_type.

    Raises:
        AuthenticationError: If credentials are invalid.
    """
    if not authenticate_user(form_data.username, form_data.password):
        logger.warning(
            "login_failed",
            username=form_data.username,
            reason="invalid_credentials",
        )
        raise AuthenticationError("Invalid username or password")

    access_token = create_access_token(data={"sub": form_data.username})

    logger.info("login_success", username=form_data.username)

    return Token(access_token=access_token)


@router.post("/login/json", response_model=Token)
async def login_json(request: LoginRequest) -> Token:
    """
    Authenticate user via JSON body and return JWT token.

    Alternative to form-based login for API clients.

    Returns:
        Token with access_token and token_type.

    Raises:
        AuthenticationError: If credentials are invalid.
    """
    if not authenticate_user(request.username, request.password):
        logger.warning(
            "login_failed",
            username=request.username,
            reason="invalid_credentials",
        )
        raise AuthenticationError("Invalid username or password")

    access_token = create_access_token(data={"sub": request.username})

    logger.info("login_success", username=request.username)

    return Token(access_token=access_token)


@router.get("/me")
async def get_me(current_user: TokenData = Depends(get_current_user)):
    """
    Get current authenticated user information.

    Returns:
        User information from the JWT token.
    """
    return {
        "username": current_user.username,
        "authenticated": True,
    }


@router.post("/verify")
async def verify_token(current_user: TokenData = Depends(get_current_user)):
    """
    Verify that the current token is valid.

    Returns:
        Verification status.
    """
    return {
        "valid": True,
        "username": current_user.username,
    }
