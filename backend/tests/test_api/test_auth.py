"""Tests for authentication endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestAuthEndpoints:
    """Test authentication endpoints."""

    def test_login_success(self, client: TestClient):
        """Test successful login with valid credentials."""
        response = client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "admin"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_json_success(self, client: TestClient):
        """Test successful login via JSON endpoint."""
        response = client.post(
            "/api/auth/login/json",
            json={"username": "admin", "password": "admin"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_username(self, client: TestClient):
        """Test login with invalid username."""
        response = client.post(
            "/api/auth/login",
            data={"username": "invalid", "password": "admin"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "AUTHENTICATION_ERROR"

    def test_login_invalid_password(self, client: TestClient):
        """Test login with invalid password."""
        response = client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "wrong"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "AUTHENTICATION_ERROR"

    def test_get_me_authenticated(self, client: TestClient, auth_headers: dict):
        """Test getting current user info when authenticated."""
        response = client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert data["authenticated"] is True

    def test_get_me_unauthenticated(self, client: TestClient):
        """Test getting current user info without authentication."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "AUTHENTICATION_ERROR"

    def test_verify_token_valid(self, client: TestClient, auth_headers: dict):
        """Test token verification with valid token."""
        response = client.post("/api/auth/verify", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["username"] == "admin"

    def test_verify_token_invalid(self, client: TestClient):
        """Test token verification with invalid token."""
        response = client.post(
            "/api/auth/verify",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401
