from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# Create sync engine (using psycopg2)
# Convert postgresql:// to postgresql+psycopg2:// if needed
database_url = settings.database_url
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for getting database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Run database migrations to ensure schema is up to date."""
    import os

    from sqlalchemy import text

    from alembic import command
    from alembic.config import Config

    # Get the path to alembic.ini
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alembic_ini = os.path.join(backend_dir, "alembic.ini")

    if os.path.exists(alembic_ini):
        alembic_cfg = Config(alembic_ini)
        alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))

        # Check if this is a pre-existing database without alembic_version
        # If tables exist but no alembic_version, stamp as initial migration
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'servers')"
                )
            )
            servers_exists = result.scalar()

            result = conn.execute(
                text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'alembic_version')"
                )
            )
            alembic_exists = result.scalar()

            if servers_exists and not alembic_exists:
                # Database has tables but no alembic tracking - stamp it
                command.stamp(alembic_cfg, "001_initial")
            else:
                # Run migrations normally
                command.upgrade(alembic_cfg, "head")
    else:
        # Fallback to create_all for development without alembic.ini
        from app.models import Base

        Base.metadata.create_all(bind=engine)
