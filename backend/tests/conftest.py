"""Pytest fixtures for Jarvis backend tests."""

import pytest
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db, Base
from app.core.security import create_access_token

# Use SQLite in-memory for tests
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_db() -> Generator[Session, None, None]:
    """Create a fresh test database for each test."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Override the get_db dependency
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        app.dependency_overrides.clear()


@pytest.fixture
def client(test_db: Session) -> TestClient:
    """Create a test client with test database."""
    return TestClient(app)


@pytest.fixture
def auth_token() -> str:
    """Create a valid authentication token for tests."""
    return create_access_token(data={"sub": "admin"})


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    """Create authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def mock_ollama_service(mocker) -> MagicMock:
    """Mock OllamaService for tests that don't need real LLM."""
    mock = mocker.patch("app.services.ollama.OllamaService")
    instance = mock.return_value
    instance.chat = AsyncMock(return_value="Mocked response")
    instance.chat_stream = AsyncMock()
    instance.health_check = AsyncMock(return_value=True)
    instance.list_models = AsyncMock(return_value=[])
    return instance


@pytest.fixture
def mock_ssh_service(mocker) -> MagicMock:
    """Mock SSHService for tests that don't need real SSH."""
    mock = mocker.patch("app.services.ssh.SSHService")
    instance = mock.return_value
    instance.connect = MagicMock(return_value=True)
    instance.disconnect = MagicMock()
    instance.execute_command = MagicMock(return_value=("stdout", "stderr", 0))
    instance.get_system_info = MagicMock(
        return_value={
            "os": "Linux",
            "kernel": "5.15.0",
            "hostname": "test-server",
        }
    )
    return instance


@pytest.fixture
def mock_search_service(mocker) -> MagicMock:
    """Mock SearchService for tests that don't need real search."""
    mock = mocker.patch("app.services.search.SearchService")
    instance = mock.return_value
    instance.search = AsyncMock(return_value=[])
    instance.health_check = AsyncMock(return_value=True)
    return instance


@pytest.fixture
def sample_server_data() -> dict:
    """Sample server data for tests."""
    return {
        "hostname": "test-server",
        "ip_address": "10.10.20.100",
        "username": "testuser",
        "password": "testpass",
        "port": 22,
    }
