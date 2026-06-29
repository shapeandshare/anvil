"""Tests for health check and service management API endpoints.

Covers GET /v1/health, GET /v1/health/detailed, GET /v1/services,
GET /v1/services/logs/{name}, POST /v1/services/restart-all,
POST /v1/services/logs/{name}/clear, POST /v1/services/{name}/start,
POST /v1/services/{name}/stop, POST /v1/services/{name}/restart,
POST /v1/services/{name}/kill-port, POST /v1/demo/bootstrap,
and GET /v1/csrf-token.
"""

from __future__ import annotations

import os
import signal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from anvil.api.app import app
from anvil.api.deps import get_workbench

####################################################################
# Fixtures
####################################################################


@pytest.fixture
def mock_mlflow():
    """Create a mock MLflowService with the protocol used by health_ops.

    Provides ``start()``, ``async_stop()``, ``is_running`` property,
    and ``tracking_uri``.
    """
    mlflow = MagicMock()
    mlflow.is_running = False
    mlflow.async_stop = AsyncMock()
    mlflow.start = MagicMock()
    mlflow.tracking_uri = "http://127.0.0.1:5001"
    return mlflow


@pytest.fixture
def mlflow_running(mock_mlflow):
    """Set ``app.state.mlflow`` to a running mock."""
    mock_mlflow.is_running = True
    app.state.mlflow = mock_mlflow
    yield
    app.state.mlflow = None


@pytest.fixture
def mlflow_stopped(mock_mlflow):
    """Set ``app.state.mlflow`` to a stopped mock."""
    mock_mlflow.is_running = False
    app.state.mlflow = mock_mlflow
    yield
    app.state.mlflow = None


@pytest.fixture
def mlflow_none():
    """Set ``app.state.mlflow`` to ``None``."""
    app.state.mlflow = None
    yield
    app.state.mlflow = None


@pytest.fixture
def mock_workbench():
    """Create a mock ``AnvilWorkbench`` with a mock demo service."""
    wb = MagicMock()
    demo_result = MagicMock()
    demo_result.model_dump.return_value = {
        "corpora_created": 2,
        "datasets_created": 1,
        "corpora_skipped": 0,
        "datasets_skipped": 0,
        "errors": [],
        "total_time_ms": 123,
    }
    wb.demo = MagicMock()
    wb.demo.bootstrap_all = AsyncMock(return_value=demo_result)
    return wb


@pytest.fixture
def override_dep(mock_workbench):
    """Override the ``get_workbench`` dependency for bootstrap tests."""
    app.dependency_overrides[get_workbench] = lambda: mock_workbench
    yield
    app.dependency_overrides.clear()


####################################################################
# GET /v1/health
####################################################################


class TestHealth:
    """Bare liveness health check — auth-exempt, no dependencies."""

    async def test_returns_healthy(self, client) -> None:
        """GET /v1/health returns ``{"status": "healthy"}``."""
        resp = await client.get("/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}


####################################################################
# GET /v1/health/detailed
####################################################################


class TestHealthDetailed:
    """Detailed system health — requires auth, uses psutil/MigrationService."""

    async def test_returns_detailed_structure(self, client) -> None:
        """GET /v1/health/detailed returns all expected sections."""
        resp = await client.get("/v1/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert isinstance(data["version"], str)
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], int)
        assert data["uptime_seconds"] >= 0

        # System block
        system = data["system"]
        assert "cpu_percent" in system
        assert "memory_percent" in system
        assert "memory_used_gb" in system
        assert "memory_total_gb" in system
        assert "disk_percent" in system
        assert "disk_used_gb" in system
        assert "disk_total_gb" in system

        # GPU block
        gpu = data["gpu"]
        assert "available" in gpu
        assert "backend" in gpu
        assert "device_name" in gpu
        assert "memory_total_gb" in gpu
        assert "memory_available_gb" in gpu
        assert "compute_capability" in gpu
        assert "torch_version" in gpu
        assert "cuda_version" in gpu
        assert "errors" in gpu

        # Database block
        db = data["database"]
        assert "status" in db
        assert "schema_version" in db
        assert "expected_schema_version" in db
        assert "migration_revision" in db
        assert db["expected_schema_version"] >= 0

        # MLflow block
        mlf = data["mlflow"]
        assert "status" in mlf

        # Docs
        docs = data["docs"]
        assert "swagger" in docs
        assert "redoc" in docs


####################################################################
# GET /v1/services
####################################################################


class TestListServices:
    """List managed services with their statuses."""

    async def test_with_mlflow_running(self, client, mlflow_running) -> None:
        """Both services listed, MLflow status is "running"."""
        resp = await client.get("/v1/services")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["services"]) == 2
        assert data["services"][0] == {"name": "web", "status": "running"}
        assert data["services"][1]["name"] == "mlflow"
        assert data["services"][1]["status"] == "running"
        assert "port" in data["services"][1]
        assert "mlflow_url" in data["services"][1]

    async def test_with_mlflow_stopped(self, client, mlflow_stopped) -> None:
        """MLflow service exists but is not running."""
        resp = await client.get("/v1/services")
        assert resp.status_code == 200
        data = resp.json()
        assert data["services"][1]["status"] == "stopped"

    async def test_without_mlflow_object(self, client, mlflow_none) -> None:
        """No MLflow object on app state — status defaults to "stopped"."""
        resp = await client.get("/v1/services")
        assert resp.status_code == 200
        data = resp.json()
        # When mlflow is None and mlflow_disable_local is false → "stopped"
        assert data["services"][1]["status"] == "stopped"


####################################################################
# GET /v1/services/logs/{name}
####################################################################


class TestServiceLogs:
    """Retrieve the last N lines of a service log file."""

    async def _make_log(
        self, tmp_path: Path, name: str, lines: list[str]
    ) -> Path:
        """Create a log file under tmp_path/logs/{name}.log."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"{name}.log"
        log_file.write_text("\n".join(lines) + "\n")
        return log_file

    async def test_get_existing_logs(self, client, monkeypatch, tmp_path) -> None:
        """Returns full log contents when the log file exists."""
        monkeypatch.chdir(tmp_path)
        await self._make_log(tmp_path, "web", ["line1", "line2", "line3"])
        resp = await client.get("/v1/services/logs/web")
        assert resp.status_code == 200
        assert resp.json() == {"logs": ["line1", "line2", "line3"]}

    async def test_get_logs_respects_lines_param(
        self, client, monkeypatch, tmp_path
    ) -> None:
        """Respects the ``lines`` query parameter to trim output."""
        monkeypatch.chdir(tmp_path)
        await self._make_log(tmp_path, "web", ["a", "b", "c", "d", "e"])
        resp = await client.get("/v1/services/logs/web", params={"lines": 2})
        assert resp.status_code == 200
        assert resp.json() == {"logs": ["d", "e"]}

    async def test_logs_defaults_to_50_lines(
        self, client, monkeypatch, tmp_path
    ) -> None:
        """Default ``lines`` is 50 when not specified."""
        monkeypatch.chdir(tmp_path)
        lines = [str(i) for i in range(60)]
        await self._make_log(tmp_path, "mlflow", lines)
        resp = await client.get("/v1/services/logs/mlflow")
        assert resp.status_code == 200
        assert len(resp.json()["logs"]) == 50
        assert resp.json()["logs"][0] == "10"
        assert resp.json()["logs"][-1] == "59"

    async def test_missing_log_file(self, client, monkeypatch, tmp_path) -> None:
        """Empty log directory — returns empty list, not an error."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir()
        resp = await client.get("/v1/services/logs/web")
        assert resp.status_code == 200
        assert resp.json() == {"logs": []}

    async def test_missing_log_directory(self, client, monkeypatch, tmp_path) -> None:
        """No logs directory at all — returns empty list."""
        monkeypatch.chdir(tmp_path)
        resp = await client.get("/v1/services/logs/web")
        assert resp.status_code == 200
        assert resp.json() == {"logs": []}

    async def test_unknown_service_returns_404(self, client) -> None:
        """An unrecognised service name causes a 404."""
        resp = await client.get("/v1/services/logs/unknownsvc")
        assert resp.status_code == 404
        assert "Unknown service" in resp.json()["detail"]


####################################################################
# POST /v1/services/restart-all
####################################################################


class TestRestartAllServices:
    """Restart all managed services."""

    async def test_restart_with_mlflow_running(
        self, client, mlflow_running
    ) -> None:
        """Running MLflow is stopped then started."""
        mlflow = app.state.mlflow
        resp = await client.post("/v1/services/restart-all")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["results"]["mlflow"] == "restarted"
        assert resp.json()["results"]["web"] == "cannot_manage"
        mlflow.async_stop.assert_awaited_once()
        mlflow.start.assert_called_once()

    async def test_restart_with_mlflow_stopped(
        self, client, mlflow_stopped
    ) -> None:
        """Stopped MLflow is started (async_stop not called)."""
        mlflow = app.state.mlflow
        resp = await client.post("/v1/services/restart-all")
        assert resp.status_code == 200
        assert resp.json()["results"]["mlflow"] == "restarted"
        mlflow.async_stop.assert_not_called()
        mlflow.start.assert_called_once()

    async def test_restart_without_mlflow(self, client, mlflow_none) -> None:
        """No MLflow object — returns 'not_initialized'."""
        resp = await client.post("/v1/services/restart-all")
        assert resp.status_code == 200
        assert resp.json()["results"]["mlflow"] == "not_initialized"


####################################################################
# POST /v1/services/logs/{name}/clear
####################################################################


class TestClearServiceLogs:
    """Clear a service's log file by truncating it."""

    async def test_clear_existing_logs(self, client, monkeypatch, tmp_path) -> None:
        """Existing log file is truncated."""
        monkeypatch.chdir(tmp_path)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "web.log").write_text("some content\n")
        resp = await client.post("/v1/services/logs/web/clear")
        assert resp.status_code == 200
        assert resp.json() == {"status": "cleared"}
        assert log_dir.joinpath("web.log").read_text() == ""

    async def test_clear_missing_log_file(
        self, client, monkeypatch, tmp_path
    ) -> None:
        """No log file exists — returns 'no_logs'."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir()
        resp = await client.post("/v1/services/logs/web/clear")
        assert resp.status_code == 200
        assert resp.json() == {"status": "no_logs"}

    async def test_clear_missing_log_directory(
        self, client, monkeypatch, tmp_path
    ) -> None:
        """No logs directory — returns 'no_logs'."""
        monkeypatch.chdir(tmp_path)
        resp = await client.post("/v1/services/logs/web/clear")
        assert resp.status_code == 200
        assert resp.json() == {"status": "no_logs"}

    async def test_clear_unknown_service_returns_404(self, client) -> None:
        """Unknown service name causes a 404."""
        resp = await client.post("/v1/services/logs/bogus/clear")
        assert resp.status_code == 404
        assert "Unknown service" in resp.json()["detail"]


####################################################################
# POST /v1/services/{name}/start
####################################################################


class TestStartService:
    """Start a named service."""

    async def test_start_mlflow_not_running(
        self, client, mlflow_stopped
    ) -> None:
        """Starts MLflow when it is stopped."""
        mlflow = app.state.mlflow
        resp = await client.post("/v1/services/mlflow/start")
        assert resp.status_code == 200
        assert resp.json() == {
            "status": "started",
            "name": "mlflow",
            "port": 5001,
        }
        mlflow.start.assert_called_once()

    async def test_start_mlflow_already_running(
        self, client, mlflow_running
    ) -> None:
        """Starting an already-running MLflow skips the start call."""
        mlflow = app.state.mlflow
        resp = await client.post("/v1/services/mlflow/start")
        assert resp.status_code == 200
        # When already running, start() is not called (no-op)
        mlflow.start.assert_not_called()

    async def test_start_mlflow_not_initialized(
        self, client, mlflow_none
    ) -> None:
        """MLflow not initialized — returns 400."""
        resp = await client.post("/v1/services/mlflow/start")
        assert resp.status_code == 400
        assert "not initialized" in resp.json()["detail"]

    async def test_start_unknown_service(self, client) -> None:
        """Unknown service name returns 404."""
        resp = await client.post("/v1/services/elasticsearch/start")
        assert resp.status_code == 404
        assert "Unknown service" in resp.json()["detail"]


####################################################################
# POST /v1/services/{name}/stop
####################################################################


class TestStopService:
    """Stop a named service."""

    async def test_stop_mlflow_running(self, client, mlflow_running) -> None:
        """Stops MLflow when it is running."""
        mlflow = app.state.mlflow
        resp = await client.post("/v1/services/mlflow/stop")
        assert resp.status_code == 200
        assert resp.json() == {"status": "stopped", "name": "mlflow"}
        mlflow.async_stop.assert_awaited_once()

    async def test_stop_mlflow_not_running(
        self, client, mlflow_stopped
    ) -> None:
        """Stopping a stopped MLflow is a no-op."""
        mlflow = app.state.mlflow
        resp = await client.post("/v1/services/mlflow/stop")
        assert resp.status_code == 200
        mlflow.async_stop.assert_not_called()

    async def test_stop_mlflow_not_initialized(
        self, client, mlflow_none
    ) -> None:
        """MLflow not initialized — returns 400."""
        resp = await client.post("/v1/services/mlflow/stop")
        assert resp.status_code == 400
        assert "not initialized" in resp.json()["detail"]

    async def test_stop_unknown_service(self, client) -> None:
        """Unknown service name returns 404."""
        resp = await client.post("/v1/services/elasticsearch/stop")
        assert resp.status_code == 404
        assert "Unknown service" in resp.json()["detail"]


####################################################################
# POST /v1/services/{name}/restart
####################################################################


class TestRestartService:
    """Restart a named service."""

    async def test_restart_mlflow_running(
        self, client, mlflow_running
    ) -> None:
        """Running MLflow is restarted (stopped then started)."""
        mlflow = app.state.mlflow
        resp = await client.post("/v1/services/mlflow/restart")
        assert resp.status_code == 200
        assert resp.json() == {"status": "restarted", "name": "mlflow"}
        mlflow.async_stop.assert_awaited_once()
        mlflow.start.assert_called_once()

    async def test_restart_mlflow_stopped(
        self, client, mlflow_stopped
    ) -> None:
        """Stopped MLflow is started."""
        mlflow = app.state.mlflow
        resp = await client.post("/v1/services/mlflow/restart")
        assert resp.status_code == 200
        mlflow.async_stop.assert_not_called()
        mlflow.start.assert_called_once()

    async def test_restart_mlflow_not_initialized(
        self, client, mlflow_none
    ) -> None:
        """MLflow not initialized — returns 400."""
        resp = await client.post("/v1/services/mlflow/restart")
        assert resp.status_code == 400
        assert "not initialized" in resp.json()["detail"]

    async def test_restart_unknown_service(self, client) -> None:
        """Unknown service name returns 404."""
        resp = await client.post("/v1/services/redis/restart")
        assert resp.status_code == 404
        assert "Unknown service" in resp.json()["detail"]


####################################################################
# POST /v1/services/{name}/kill-port
####################################################################


class TestKillServicePort:
    """Kill processes occupying a service's port."""

    async def test_kill_mlflow_port_no_processes(
        self, client, mlflow_none
    ) -> None:
        """Port is scanned; no processes found — returns empty killed list."""
        with (
            patch("anvil.api.v1.health_ops._poll_port", return_value=[]),
            patch("anvil.api.v1.health_ops.os.kill") as mock_kill,
        ):
            resp = await client.post("/v1/services/mlflow/kill-port")
        assert resp.status_code == 200
        assert resp.json()["status"] == "killed"
        assert resp.json()["killed"] == []
        assert resp.json()["port"] == 5001
        mock_kill.assert_not_called()

    async def test_kill_mlflow_port_kills_processes(
        self, client, mlflow_none
    ) -> None:
        """Found PIDs are killed with SIGKILL."""
        with (
            patch("anvil.api.v1.health_ops._poll_port", return_value=[1234, 5678]),
            patch("anvil.api.v1.health_ops.os.kill") as mock_kill,
        ):
            resp = await client.post("/v1/services/mlflow/kill-port")
        assert resp.status_code == 200
        assert resp.json()["killed"] == [1234, 5678]
        calls = [call(1234, signal.SIGKILL), call(5678, signal.SIGKILL)]
        mock_kill.assert_has_calls(calls, any_order=True)

    async def test_kill_mlflow_port_skips_missing_pids(
        self, client, mlflow_none
    ) -> None:
        """ProcessLookupError for a PID is silently skipped."""
        with (
            patch("anvil.api.v1.health_ops._poll_port", return_value=[42, 99]),
            patch(
                "anvil.api.v1.health_ops.os.kill",
                side_effect=[None, ProcessLookupError],
            ) as mock_kill,
        ):
            resp = await client.post("/v1/services/mlflow/kill-port")
        assert resp.status_code == 200
        # PID 42 killed, PID 99 skipped
        assert resp.json()["killed"] == [42]

    async def test_kill_unknown_service(self, client) -> None:
        """Unknown service name returns 404 before scanning."""
        resp = await client.post("/v1/services/nginx/kill-port")
        assert resp.status_code == 404
        assert "Unknown service" in resp.json()["detail"]

    async def test_kill_port_invalid_service_name(self, client) -> None:
        """Invalid service name with path traversal attempts."""
        # Use URL-encoded path traversal — FastAPI extracts as-is
        resp = await client.post("/v1/services/../etc/kill-port")
        # This won't match the route, should return 404
        assert resp.status_code == 404


####################################################################
# POST /v1/demo/bootstrap
####################################################################


class TestBootstrap:
    """Re-bootstrap demo data."""

    async def test_bootstrap_success(
        self, client, mock_workbench, override_dep
    ) -> None:
        """Returns bootstrap result from workbench."""
        resp = await client.post("/v1/demo/bootstrap")
        assert resp.status_code == 200
        data = resp.json()
        assert data["corpora_created"] == 2
        assert data["datasets_created"] == 1
        assert data["corpora_skipped"] == 0
        assert data["errors"] == []
        assert data["total_time_ms"] == 123
        mock_workbench.demo.bootstrap_all.assert_awaited_once()

    async def test_bootstrap_concurrent_attempt(
        self, client, mock_workbench, override_dep
    ) -> None:
        """Concurrent bootstrap attempt returns 409."""
        # First request succeeds
        resp1 = await client.post("/v1/demo/bootstrap")
        assert resp1.status_code == 200
        # Second request while first is "in progress" — but since the first
        # already completed, we need a different way to trigger the 409.
        # The _bootstrap_in_progress flag is module-level, so we can set it.
        import anvil.api.v1.health_ops as ho

        ho._bootstrap_in_progress = True
        try:
            resp2 = await client.post("/v1/demo/bootstrap")
            assert resp2.status_code == 409
            assert resp2.json()["detail"]["status"] == "busy"
        finally:
            ho._bootstrap_in_progress = False


####################################################################
# GET /v1/csrf-token
####################################################################


class TestCsrfToken:
    """CSRF token generation for the current session."""

    async def test_with_session_cookie(self, client) -> None:
        """Returns a non-empty token when a session cookie is present."""
        resp = await client.get(
            "/v1/csrf-token",
            cookies={"anvil_session": "test-session-id-123"},
        )
        assert resp.status_code == 200
        token = resp.json()["token"]
        assert isinstance(token, str)
        assert len(token) > 0

    async def test_without_session_cookie(self, client) -> None:
        """Returns an empty token when no session cookie is present."""
        resp = await client.get("/v1/csrf-token")
        assert resp.status_code == 200
        assert resp.json()["token"] == ""