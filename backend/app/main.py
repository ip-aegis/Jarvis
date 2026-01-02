from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError as PydanticValidationError

from app.config import get_settings
from app.database import init_db
from app.api.routes import servers, monitoring, projects, chat, dashboard, health, auth
from app.core.exceptions import JarvisException
from app.core.error_handlers import (
    jarvis_exception_handler,
    pydantic_validation_handler,
    generic_exception_handler,
)
from app.core.logging import setup_logging, get_logger
from app.core.middleware import RequestLoggingMiddleware
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

settings = get_settings()

# Initialize structured logging
setup_logging(debug=settings.debug)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("application_startup", app_name=settings.app_name)
    init_db()
    logger.info("database_initialized")
    yield
    # Shutdown
    logger.info("application_shutdown")


app = FastAPI(
    title=settings.app_name,
    description="AI/LLM-enabled lab monitoring and management",
    version="0.1.0",
    root_path="",
    lifespan=lifespan,
)

# CORS middleware - restrict to configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)

# Request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Rate limiting
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# Register exception handlers
app.add_exception_handler(JarvisException, jarvis_exception_handler)
app.add_exception_handler(PydanticValidationError, pydantic_validation_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(servers.router, prefix="/api/servers", tags=["servers"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["monitoring"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])


@app.get("/")
async def root():
    return {"message": "Jarvis API", "version": "0.1.0"}
