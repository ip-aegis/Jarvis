from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError as PydanticValidationError
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import (
    actions,
    auth,
    chat,
    dashboard,
    health,
    home,
    journal,
    monitoring,
    network,
    projects,
    servers,
    work,
)
from app.api.routes import settings as settings_routes
from app.config import get_settings
from app.core.error_handlers import (
    generic_exception_handler,
    jarvis_exception_handler,
    pydantic_validation_handler,
)
from app.core.exceptions import JarvisException
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestLoggingMiddleware
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.database import init_db

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

    # Register infrastructure actions (done here to avoid circular imports)
    try:
        from app.tools.infrastructure_actions import register_infrastructure_actions

        register_infrastructure_actions()
        logger.info("infrastructure_actions_registered")
    except Exception as e:
        logger.warning("infrastructure_actions_registration_failed", error=str(e))

    # Start home automation background tasks
    try:
        from app.services.home.background_tasks import start_background_tasks, stop_background_tasks

        await start_background_tasks()
        logger.info("home_automation_tasks_started")
    except Exception as e:
        logger.warning("home_automation_startup_failed", error=str(e))

    yield

    # Shutdown
    try:
        from app.services.home.background_tasks import stop_background_tasks

        await stop_background_tasks()
        logger.info("home_automation_tasks_stopped")
    except Exception as e:
        logger.warning("home_automation_shutdown_failed", error=str(e))

    logger.info("application_shutdown")


app = FastAPI(
    title=settings.app_name,
    description="AI/LLM-enabled lab monitoring and management",
    version="0.1.0",
    root_path="",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
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
app.include_router(network.router, prefix="/api/network", tags=["network"])
app.include_router(actions.router, prefix="/api/actions", tags=["actions"])
app.include_router(home.router, prefix="/api/home", tags=["home"])
app.include_router(journal.router, prefix="/api/journal", tags=["journal"])
app.include_router(work.router, prefix="/api/work", tags=["work"])
app.include_router(settings_routes.router, prefix="/api/settings", tags=["settings"])


@app.get("/")
async def root():
    return {"message": "Jarvis API", "version": "0.1.0"}
