"""Tests for monitoring API endpoints."""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Metric, Server


class TestGetAllMetrics:
    """Tests for GET /api/monitoring endpoint."""

    def test_get_all_metrics_empty(self, client: TestClient, auth_headers: dict):
        """Should return empty metrics list when no servers exist."""
        response = client.get("/api/monitoring/", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == {"metrics": []}

    def test_get_all_metrics_with_data(
        self, client: TestClient, auth_headers: dict, test_db: Session
    ):
        """Should return metrics for all servers."""
        # Create server
        server = Server(
            hostname="test-server",
            ip_address="10.10.20.100",
            username="testuser",
            status="online",
        )
        test_db.add(server)
        test_db.commit()

        # Create metric
        metric = Metric(
            server_id=server.id,
            cpu_usage=45.5,
            memory_percent=60.2,
            disk_percent=75.0,
            gpu_utilization=None,
        )
        test_db.add(metric)
        test_db.commit()

        response = client.get("/api/monitoring/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["metrics"]) == 1
        assert data["metrics"][0]["hostname"] == "test-server"
        assert data["metrics"][0]["cpu_usage"] == 45.5


class TestGetServerMetrics:
    """Tests for GET /api/monitoring/{server_id} endpoint."""

    def test_get_server_metrics_not_found(self, client: TestClient, auth_headers: dict):
        """Should return 404 for non-existent server."""
        response = client.get("/api/monitoring/999", headers=auth_headers)
        assert response.status_code == 404

    def test_get_server_metrics_no_data(
        self, client: TestClient, auth_headers: dict, test_db: Session
    ):
        """Should return default values when no metrics exist."""
        server = Server(
            hostname="test-server",
            ip_address="10.10.20.100",
            username="testuser",
            status="online",
            cpu_cores=8,
        )
        test_db.add(server)
        test_db.commit()

        response = client.get(f"/api/monitoring/{server.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["hostname"] == "test-server"
        assert data["cpu"]["usage"] == 0
        assert data["memory"]["percent"] == 0

    def test_get_server_metrics_with_data(
        self, client: TestClient, auth_headers: dict, test_db: Session
    ):
        """Should return detailed server metrics."""
        server = Server(
            hostname="test-server",
            ip_address="10.10.20.100",
            username="testuser",
            status="online",
            cpu_cores=8,
        )
        test_db.add(server)
        test_db.commit()

        metric = Metric(
            server_id=server.id,
            cpu_usage=45.5,
            cpu_per_core={"cpu0": 50.0, "cpu1": 40.0},
            memory_used=8000000000,
            memory_total=16000000000,
            memory_percent=50.0,
            memory_available=8000000000,
            disk_used=250000000000,
            disk_total=500000000000,
            disk_percent=50.0,
            gpu_utilization=75.0,
            gpu_memory_used=4000000000,
            gpu_memory_total=8000000000,
            gpu_temperature=65.0,
            load_avg_1m=1.5,
            load_avg_5m=1.2,
            load_avg_15m=1.0,
        )
        test_db.add(metric)
        test_db.commit()

        response = client.get(f"/api/monitoring/{server.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["cpu"]["usage"] == 45.5
        assert data["cpu"]["per_core"]["cpu0"] == 50.0
        assert data["memory"]["percent"] == 50.0
        assert data["gpu"]["utilization"] == 75.0
        assert data["gpu"]["temperature"] == 65.0


class TestGetMetricsHistory:
    """Tests for GET /api/monitoring/{server_id}/history endpoint."""

    def test_get_history_server_not_found(self, client: TestClient, auth_headers: dict):
        """Should return 404 for non-existent server."""
        response = client.get("/api/monitoring/999/history", headers=auth_headers)
        assert response.status_code == 404

    def test_get_history_empty(self, client: TestClient, auth_headers: dict, test_db: Session):
        """Should return empty data when no history exists."""
        server = Server(
            hostname="test-server",
            ip_address="10.10.20.100",
            username="testuser",
            status="online",
        )
        test_db.add(server)
        test_db.commit()

        response = client.get(
            f"/api/monitoring/{server.id}/history?metric=cpu",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
        assert data["metric"] == "cpu"

    def test_get_history_with_data(self, client: TestClient, auth_headers: dict, test_db: Session):
        """Should return historical metrics."""
        server = Server(
            hostname="test-server",
            ip_address="10.10.20.100",
            username="testuser",
            status="online",
        )
        test_db.add(server)
        test_db.commit()

        # Add metrics at different times
        now = datetime.utcnow()
        for i in range(5):
            metric = Metric(
                server_id=server.id,
                timestamp=now - timedelta(hours=i),
                cpu_usage=40.0 + i * 5,
                memory_percent=50.0,
            )
            test_db.add(metric)
        test_db.commit()

        response = client.get(
            f"/api/monitoring/{server.id}/history?metric=cpu&hours=24",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 5
        assert data["hours"] == 24


class TestAgentReport:
    """Tests for POST /api/monitoring/agent/report endpoint."""

    def test_agent_report_server_not_found(self, client: TestClient, auth_headers: dict):
        """Should return 404 for unknown server."""
        response = client.post(
            "/api/monitoring/agent/report",
            json={"server_id": 999},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_agent_report_success(self, client: TestClient, auth_headers: dict, test_db: Session):
        """Should save metrics and return success."""
        server = Server(
            hostname="test-server",
            ip_address="10.10.20.100",
            username="testuser",
            status="offline",
        )
        test_db.add(server)
        test_db.commit()

        response = client.post(
            "/api/monitoring/agent/report",
            json={
                "server_id": server.id,
                "hostname": "test-server",
                "cpu": {"usage": 55.0, "per_core": {"cpu0": 60.0, "cpu1": 50.0}},
                "memory": {
                    "total": 16000000000,
                    "used": 8000000000,
                    "available": 8000000000,
                    "percent": 50.0,
                },
                "disk": {"total": 500000000000, "used": 250000000000, "percent": 50.0},
                "gpu": None,
                "load_avg": {"1m": 1.5, "5m": 1.2, "15m": 1.0},
                "temperatures": {"cpu": 65.0},
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "received"

        # Verify metric was saved
        metric = test_db.query(Metric).filter(Metric.server_id == server.id).first()
        assert metric is not None
        assert metric.cpu_usage == 55.0

        # Verify server status updated to online
        test_db.refresh(server)
        assert server.status == "online"
