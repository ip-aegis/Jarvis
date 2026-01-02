"""Tests for health check endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_liveness_probe(self, client: TestClient):
        """Test liveness probe returns alive status."""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    def test_readiness_probe(self, client: TestClient):
        """Test readiness probe with database connection."""
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_full_health_check(self, client: TestClient):
        """Test comprehensive health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()

        # Should have status and version
        assert "status" in data
        assert "version" in data
        assert data["version"] == "0.1.0"

        # Should have dependency checks
        assert "dependencies" in data
        dependencies = data["dependencies"]
        assert "database" in dependencies
        assert "ollama" in dependencies
        assert "searxng" in dependencies

        # Each dependency should have status
        for dep_name, dep_info in dependencies.items():
            assert "status" in dep_info


class TestRootEndpoint:
    """Test root API endpoint."""

    def test_root_returns_api_info(self, client: TestClient):
        """Test root endpoint returns API information."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Jarvis API"
        assert data["version"] == "0.1.0"
