"""Tests for interactive teaching loop API endpoints.

Covers all /v1/teach/* routes with mocked workbench.
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from anvil.api.app import app
from anvil.api.deps import get_workbench


def _make_session(session_id: int = 1, status: str = "active") -> MagicMock:
    s = MagicMock()
    s.id = session_id
    s.name = f"session-{session_id}"
    s.description = "A test session"
    s.seed_experiment_id = 1
    s.current_base_experiment_id = 1
    s.status = status
    s.created_at = datetime.now(UTC)
    s.updated_at = datetime.now(UTC)
    return s


@pytest.fixture
def mock_workbench():
    wb = MagicMock()
    wb.teaching = MagicMock()
    wb.tracking = MagicMock()
    return wb


@pytest.fixture
def override_dep(mock_workbench):
    app.dependency_overrides[get_workbench] = lambda: mock_workbench
    yield
    app.dependency_overrides.clear()


########################################################################
# Session CRUD
########################################################################


class TestCreateSession:
    """Tests for POST /v1/teach/sessions."""

    async def test_create_success(self, client, mock_workbench, override_dep):
        """Returns 200 with created session."""
        mock_workbench.teaching.create_session = AsyncMock(
            return_value=_make_session(session_id=1),
        )

        resp = await client.post(
            "/v1/teach/sessions",
            json={
                "name": "my-session",
                "description": "A test session",
                "seed_experiment_id": 1,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["name"] == "session-1"
        assert data["status"] == "active"
        mock_workbench.teaching.create_session.assert_awaited_with(
            name="my-session",
            description="A test session",
            seed_experiment_id=1,
        )

    async def test_create_minimal(self, client, mock_workbench, override_dep):
        """Creates session with only required fields."""
        mock_workbench.teaching.create_session = AsyncMock(
            return_value=_make_session(session_id=2, status="active"),
        )

        resp = await client.post(
            "/v1/teach/sessions",
            json={"name": "minimal"},
        )

        assert resp.status_code == 200


class TestListSessions:
    """Tests for GET /v1/teach/sessions."""

    async def test_list_all(self, client, mock_workbench, override_dep):
        """Returns paginated session list."""
        mock_workbench.teaching.list_sessions = AsyncMock(
            return_value=([_make_session(1), _make_session(2)], 2),
        )

        resp = await client.get("/v1/teach/sessions")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sessions"]) == 2
        assert data["total"] == 2

    async def test_list_with_filters(self, client, mock_workbench, override_dep):
        """Filters are passed to service."""
        mock_workbench.teaching.list_sessions = AsyncMock(return_value=([], 0))

        resp = await client.get("/v1/teach/sessions?status=active&limit=10&offset=5")

        assert resp.status_code == 200
        mock_workbench.teaching.list_sessions.assert_awaited_with(
            status="active",
            limit=10,
            offset=5,
        )

    async def test_list_empty(self, client, mock_workbench, override_dep):
        """Returns empty list."""
        mock_workbench.teaching.list_sessions = AsyncMock(return_value=([], 0))

        resp = await client.get("/v1/teach/sessions")

        assert resp.status_code == 200
        assert resp.json()["sessions"] == []


class TestGetSession:
    """Tests for GET /v1/teach/sessions/{session_id}."""

    async def test_get_found(self, client, mock_workbench, override_dep):
        """Returns session when found."""
        mock_workbench.teaching.get_session = AsyncMock(
            return_value=_make_session(session_id=5),
        )

        resp = await client.get("/v1/teach/sessions/5")

        assert resp.status_code == 200
        assert resp.json()["id"] == 5

    async def test_get_not_found(self, client, mock_workbench, override_dep):
        """Returns 404 when session not found."""
        mock_workbench.teaching.get_session = AsyncMock(return_value=None)

        resp = await client.get("/v1/teach/sessions/999")

        assert resp.status_code == 404
        assert "Session not found" in resp.json()["detail"]


class TestDeleteSession:
    """Tests for DELETE /v1/teach/sessions/{session_id}."""

    async def test_delete_success(self, client, mock_workbench, override_dep):
        """Returns 204 on successful deletion."""
        mock_workbench.teaching.delete_session = AsyncMock(return_value=True)

        resp = await client.delete("/v1/teach/sessions/1")

        assert resp.status_code == 204

    async def test_delete_not_found(self, client, mock_workbench, override_dep):
        """Returns 404 when session not found."""
        mock_workbench.teaching.delete_session = AsyncMock(return_value=False)

        resp = await client.delete("/v1/teach/sessions/999")

        assert resp.status_code == 404


class TestUpdateSessionStatus:
    """Tests for PATCH /v1/teach/sessions/{session_id}/status."""

    async def test_update_success(self, client, mock_workbench, override_dep):
        """Returns updated status."""
        session = _make_session(session_id=1)
        session.status = "archived"
        mock_workbench.teaching.update_status = AsyncMock(return_value=session)

        resp = await client.patch(
            "/v1/teach/sessions/1/status",
            json={"status": "archived"},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"
        mock_workbench.teaching.update_status.assert_awaited_with(1, "archived")

    async def test_update_not_found(self, client, mock_workbench, override_dep):
        """Returns 404 when session not found."""
        mock_workbench.teaching.update_status = AsyncMock(return_value=None)

        resp = await client.patch(
            "/v1/teach/sessions/999/status",
            json={"status": "archived"},
        )

        assert resp.status_code == 404

    async def test_update_validates_fields(self, client, mock_workbench, override_dep):
        """Pydantic validation: empty status returns 422."""
        resp = await client.patch(
            "/v1/teach/sessions/1/status",
            json={"status": ""},
        )
        assert resp.status_code == 422


class TestRollbackSession:
    """Tests for POST /v1/teach/sessions/{session_id}/rollback."""

    async def test_rollback_success(self, client, mock_workbench, override_dep):
        """Returns updated session with new base experiment."""
        session = _make_session(session_id=1)
        session.current_base_experiment_id = 3
        mock_workbench.teaching.rollback_to_round = AsyncMock(return_value=session)

        resp = await client.post(
            "/v1/teach/sessions/1/rollback",
            json={"target_experiment_id": 3},
        )

        assert resp.status_code == 200
        assert resp.json()["current_base_experiment_id"] == 3
        mock_workbench.teaching.rollback_to_round.assert_awaited_with(1, 3)

    async def test_rollback_not_found(self, client, mock_workbench, override_dep):
        """Returns 404 when session not found."""
        mock_workbench.teaching.rollback_to_round = AsyncMock(return_value=None)

        resp = await client.post(
            "/v1/teach/sessions/999/rollback",
            json={"target_experiment_id": 1},
        )

        assert resp.status_code == 404


########################################################################
# Rounds
########################################################################


class TestStartRound:
    """Tests for POST /v1/teach/sessions/{session_id}/rounds."""

    async def test_start_success(self, client, mock_workbench, override_dep):
        """Returns round result."""
        mock_workbench.teaching.get_session = AsyncMock(
            return_value=_make_session(session_id=1),
        )
        mock_workbench.teaching.start_round = AsyncMock(
            return_value={"experiment_id": 10, "status": "started"},
        )

        resp = await client.post(
            "/v1/teach/sessions/1/rounds",
            json={
                "examples": ["example 1", "example 2"],
                "training_config": {"n_embd": 16, "n_head": 4},
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["experiment_id"] == 10
        mock_workbench.teaching.start_round.assert_awaited_with(
            session_id=1,
            examples=["example 1", "example 2"],
            training_config={"n_embd": 16, "n_head": 4},
        )

    async def test_start_session_not_found(self, client, mock_workbench, override_dep):
        """Returns 404 when session not found."""
        mock_workbench.teaching.get_session = AsyncMock(return_value=None)

        resp = await client.post(
            "/v1/teach/sessions/999/rounds",
            json={
                "examples": ["test"],
                "training_config": {"n_embd": 16},
            },
        )

        assert resp.status_code == 404

    async def test_start_value_error(self, client, mock_workbench, override_dep):
        """Returns 422 when start_round raises ValueError."""
        mock_workbench.teaching.get_session = AsyncMock(
            return_value=_make_session(session_id=1),
        )
        mock_workbench.teaching.start_round = AsyncMock(
            side_effect=ValueError("Invalid config"),
        )

        resp = await client.post(
            "/v1/teach/sessions/1/rounds",
            json={
                "examples": ["test"],
                "training_config": {"n_embd": 16},
            },
        )

        assert resp.status_code == 422

    async def test_start_validates_empty_examples(
        self,
        client,
        mock_workbench,
        override_dep,
    ):
        """Pydantic validation: empty examples returns 422."""
        resp = await client.post(
            "/v1/teach/sessions/1/rounds",
            json={
                "examples": [],
                "training_config": {"n_embd": 16},
            },
        )
        assert resp.status_code == 422


class TestListRounds:
    """Tests for GET /v1/teach/sessions/{session_id}/rounds."""

    async def test_list_rounds(self, client, mock_workbench, override_dep):
        """Returns filtered and sorted rounds."""
        mock_workbench.teaching.get_session = AsyncMock(
            return_value=_make_session(session_id=1),
        )
        mock_workbench.tracking.list_experiments = AsyncMock(
            return_value=[
                {
                    "id": 10,
                    "mlflow_run_id": "run_1",
                    "tags": {
                        "teaching_session_id": "1",
                        "teaching_round_index": "1",
                    },
                    "status": "FINISHED",
                    "final_loss": 0.5,
                    "created_at": "1000",
                },
                {
                    "id": 11,
                    "mlflow_run_id": "run_2",
                    "tags": {
                        "teaching_session_id": "1",
                        "teaching_round_index": "0",
                    },
                    "status": "FINISHED",
                    "final_loss": 0.6,
                    "created_at": "500",
                },
            ],
        )

        resp = await client.get("/v1/teach/sessions/1/rounds")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["rounds"]) == 2
        # Round 0 should come first (sorted by round_index)
        assert data["rounds"][0]["round_index"] == "0"
        assert data["rounds"][1]["round_index"] == "1"

    async def test_list_rounds_session_not_found(
        self,
        client,
        mock_workbench,
        override_dep,
    ):
        """Returns 404 when session not found."""
        mock_workbench.teaching.get_session = AsyncMock(return_value=None)

        resp = await client.get("/v1/teach/sessions/999/rounds")

        assert resp.status_code == 404

    async def test_list_rounds_empty(self, client, mock_workbench, override_dep):
        """Returns empty rounds list when none match."""
        mock_workbench.teaching.get_session = AsyncMock(
            return_value=_make_session(session_id=1),
        )
        mock_workbench.tracking.list_experiments = AsyncMock(return_value=[])

        resp = await client.get("/v1/teach/sessions/1/rounds")

        assert resp.status_code == 200
        assert resp.json()["rounds"] == []


########################################################################
# Inspection and Comparison
########################################################################


class TestInspectRound:
    """Tests for POST /v1/teach/sessions/{session_id}/rounds/{round_index}/inspect."""

    async def test_inspect_success(self, client, mock_workbench, override_dep):
        """Returns inspection results."""
        mock_workbench.teaching.get_session = AsyncMock(
            return_value=_make_session(session_id=1),
        )
        mock_workbench.teaching.inspect_round = AsyncMock(
            return_value={
                "results": [
                    {"prompt": "hello", "output": "world"},
                ],
            },
        )

        resp = await client.post(
            "/v1/teach/sessions/1/rounds/1/inspect",
            json={
                "experiment_id": 10,
                "prompts": ["hello"],
                "temperature": 0.5,
                "max_tokens": 50,
            },
        )

        assert resp.status_code == 200
        assert "results" in resp.json()
        mock_workbench.teaching.inspect_round.assert_awaited_with(
            experiment_id=10,
            prompts=["hello"],
            temperature=0.5,
            max_tokens=50,
        )

    async def test_inspect_session_not_found(
        self,
        client,
        mock_workbench,
        override_dep,
    ):
        """Returns 404 when session not found."""
        mock_workbench.teaching.get_session = AsyncMock(return_value=None)

        resp = await client.post(
            "/v1/teach/sessions/999/rounds/1/inspect",
            json={
                "experiment_id": 10,
                "prompts": ["hello"],
            },
        )

        assert resp.status_code == 404

    async def test_inspect_value_error(self, client, mock_workbench, override_dep):
        """Returns 422 when inspect_round raises ValueError."""
        mock_workbench.teaching.get_session = AsyncMock(
            return_value=_make_session(session_id=1),
        )
        mock_workbench.teaching.inspect_round = AsyncMock(
            side_effect=ValueError("Model not found"),
        )

        resp = await client.post(
            "/v1/teach/sessions/1/rounds/1/inspect",
            json={
                "experiment_id": 999,
                "prompts": ["hello"],
            },
        )

        assert resp.status_code == 422


class TestCompareRounds:
    """Tests for POST /v1/teach/sessions/compare."""

    async def test_compare_success(self, client, mock_workbench, override_dep):
        """Returns comparison results."""
        mock_workbench.teaching.compare_rounds = AsyncMock(
            return_value={
                "results": [
                    {
                        "prompt": "hello",
                        "left_output": "world",
                        "right_output": "there",
                    },
                ],
            },
        )

        resp = await client.post(
            "/v1/teach/sessions/compare",
            json={
                "left_experiment_id": 1,
                "right_experiment_id": 2,
                "prompts": ["hello"],
                "temperature": 0.7,
                "max_tokens": 100,
            },
        )

        assert resp.status_code == 200
        assert "results" in resp.json()
        mock_workbench.teaching.compare_rounds.assert_awaited_with(
            left_experiment_id=1,
            right_experiment_id=2,
            prompts=["hello"],
            temperature=0.7,
            max_tokens=100,
        )

    async def test_compare_value_error(self, client, mock_workbench, override_dep):
        """Returns 422 when compare_rounds raises ValueError."""
        mock_workbench.teaching.compare_rounds = AsyncMock(
            side_effect=ValueError("Invalid comparison"),
        )

        resp = await client.post(
            "/v1/teach/sessions/compare",
            json={
                "left_experiment_id": 1,
                "right_experiment_id": 2,
                "prompts": ["hello"],
            },
        )

        assert resp.status_code == 422

    async def test_compare_validates_fields(self, client, mock_workbench, override_dep):
        """Pydantic validation: missing fields return 422."""
        resp = await client.post(
            "/v1/teach/sessions/compare",
            json={},
        )
        assert resp.status_code == 422
