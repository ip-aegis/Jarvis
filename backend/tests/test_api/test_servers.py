"""Tests for server management API endpoints."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Server


class TestListServers:
    """Tests for GET /api/servers endpoint."""

    def test_list_servers_empty(self, client: TestClient, auth_headers: dict):
        """Should return empty list when no servers exist."""
        response = client.get("/api/servers/", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == {"servers": []}

    def test_list_servers_with_data(self, client: TestClient, auth_headers: dict, test_db: Session):
        """Should return list of servers."""
        # Add a server directly to the database
        server = Server(
            hostname="test-server",
            ip_address="10.10.20.100",
            username="testuser",
            status="online",
            agent_installed=False,
        )
        test_db.add(server)
        test_db.commit()

        response = client.get("/api/servers/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["servers"]) == 1
        assert data["servers"][0]["hostname"] == "test-server"
        assert data["servers"][0]["ip_address"] == "10.10.20.100"


class TestGetServer:
    """Tests for GET /api/servers/{server_id} endpoint."""

    def test_get_server_not_found(self, client: TestClient, auth_headers: dict):
        """Should return 404 for non-existent server."""
        response = client.get("/api/servers/999", headers=auth_headers)
        assert response.status_code == 404

    def test_get_server_success(self, client: TestClient, auth_headers: dict, test_db: Session):
        """Should return server details."""
        server = Server(
            hostname="test-server",
            ip_address="10.10.20.100",
            username="testuser",
            status="online",
            cpu_info="Intel Core i7",
            cpu_cores=8,
        )
        test_db.add(server)
        test_db.commit()

        response = client.get(f"/api/servers/{server.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["hostname"] == "test-server"
        assert data["cpu_cores"] == 8


class TestDeleteServer:
    """Tests for DELETE /api/servers/{server_id} endpoint."""

    def test_delete_server_not_found(self, client: TestClient, auth_headers: dict):
        """Should return 404 for non-existent server."""
        response = client.delete("/api/servers/999", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_server_success(self, client: TestClient, auth_headers: dict, test_db: Session):
        """Should delete server and return success."""
        server = Server(
            hostname="test-server",
            ip_address="10.10.20.100",
            username="testuser",
            status="online",
        )
        test_db.add(server)
        test_db.commit()
        server_id = server.id

        response = client.delete(f"/api/servers/{server_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify server is deleted
        deleted = test_db.query(Server).filter(Server.id == server_id).first()
        assert deleted is None


class TestOnboardServer:
    """Tests for POST /api/servers/onboard endpoint."""

    def test_onboard_server_duplicate_ip(
        self, client: TestClient, auth_headers: dict, test_db: Session
    ):
        """Should return 400 for duplicate IP address."""
        # Add existing server
        server = Server(
            hostname="existing-server",
            ip_address="10.10.20.100",
            username="testuser",
            status="online",
        )
        test_db.add(server)
        test_db.commit()

        response = client.post(
            "/api/servers/onboard",
            headers=auth_headers,
            json={
                "credentials": {
                    "hostname": "new-server",
                    "ip_address": "10.10.20.100",
                    "username": "testuser",
                    "password": "testpass",
                    "port": 22,
                },
                "install_agent": False,
            },
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    @patch("app.api.routes.servers.SSHService")
    @patch("app.api.routes.servers.AgentService")
    @patch("app.api.routes.servers.OllamaService")
    def test_onboard_server_success(
        self,
        mock_ollama,
        mock_agent,
        mock_ssh,
        client: TestClient,
        auth_headers: dict,
        test_db: Session,
    ):
        """Should successfully onboard a new server."""
        # Setup mocks
        ssh_instance = mock_ssh.return_value
        ssh_instance.connect = AsyncMock(return_value=True)
        ssh_instance.exchange_keys = AsyncMock(return_value=True)
        ssh_instance.get_system_info = AsyncMock(
            return_value={
                "os": "Ubuntu 22.04",
                "cpu": "Intel Core i7",
                "cpu_cores": 8,
                "memory_total": "16 GB",
                "disk_total": "500 GB",
                "gpu": None,
            }
        )
        ssh_instance.disconnect = AsyncMock()
        ssh_instance.key_path = "/tmp/test_key"

        agent_instance = mock_agent.return_value
        agent_instance.install = AsyncMock(return_value=True)

        ollama_instance = mock_ollama.return_value
        ollama_instance.generate = AsyncMock(return_value="Server analysis")

        response = client.post(
            "/api/servers/onboard",
            headers=auth_headers,
            json={
                "credentials": {
                    "hostname": "new-server",
                    "ip_address": "10.10.20.200",
                    "username": "admin",
                    "password": "password123",
                    "port": 22,
                },
                "install_agent": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["hostname"] == "new-server"
        assert data["key_exchanged"] is True
        assert data["agent_installed"] is True

    @patch("app.api.routes.servers.SSHService")
    def test_onboard_server_connection_failure(
        self,
        mock_ssh,
        client: TestClient,
        auth_headers: dict,
    ):
        """Should return 400 when connection fails."""
        ssh_instance = mock_ssh.return_value
        ssh_instance.connect = AsyncMock(return_value=False)

        response = client.post(
            "/api/servers/onboard",
            headers=auth_headers,
            json={
                "credentials": {
                    "hostname": "unreachable-server",
                    "ip_address": "10.10.20.201",
                    "username": "admin",
                    "password": "password123",
                    "port": 22,
                },
                "install_agent": False,
            },
        )

        assert response.status_code == 400
        assert "Failed to connect" in response.json()["detail"]


class TestTestConnection:
    """Tests for POST /api/servers/{server_id}/test-connection endpoint."""

    def test_test_connection_server_not_found(self, client: TestClient, auth_headers: dict):
        """Should return 404 for non-existent server."""
        response = client.post("/api/servers/999/test-connection", headers=auth_headers)
        assert response.status_code == 404

    @patch("app.api.routes.servers.SSHService")
    def test_test_connection_success(
        self,
        mock_ssh,
        client: TestClient,
        auth_headers: dict,
        test_db: Session,
    ):
        """Should return connected status on success."""
        server = Server(
            hostname="test-server",
            ip_address="10.10.20.100",
            username="testuser",
            ssh_key_path="/path/to/key",
            status="offline",
        )
        test_db.add(server)
        test_db.commit()

        ssh_instance = mock_ssh.return_value
        ssh_instance.connect = AsyncMock(return_value=True)
        ssh_instance.disconnect = AsyncMock()

        response = client.post(f"/api/servers/{server.id}/test-connection", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["status"] == "connected"

        # Verify status was updated
        test_db.refresh(server)
        assert server.status == "online"
