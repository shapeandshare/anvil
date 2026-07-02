"""e2e tests for the interactive teaching loop.

Tests session CRUD via HTTP, round creation validation, and session
lifecycle.  Training rounds are validated at the HTTP boundary but
actual training execution is left to unit tests.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from anvil.db.models.teaching_session_status import TeachingSessionStatus


@pytest.fixture(autouse=True)
async def _ensure_db_tables():
    """Ensure teaching_sessions + run_id_seq tables exist."""
    from anvil.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as sess:
        try:
            await sess.execute(text("SELECT 1 FROM teaching_sessions LIMIT 1"))
        except Exception:
            from anvil.db.base import Base
            from anvil.db.session import async_engine

            async with async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        try:
            await sess.execute(text("SELECT 1 FROM run_id_seq LIMIT 1"))
        except Exception:
            await sess.execute(
                text("CREATE TABLE IF NOT EXISTS run_id_seq (next_id INTEGER NOT NULL)")
            )
            await sess.execute(text("INSERT INTO run_id_seq (next_id) VALUES (1)"))
            await sess.commit()


@pytest.mark.asyncio
async def test_create_and_get_session(client):
    """Create a teaching session via POST and retrieve via GET."""
    r = await client.post(
        "/v1/teach/sessions",
        json={"name": "my-session", "description": "My first session"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "my-session"
    assert data["status"] == TeachingSessionStatus.DRAFT
    session_id = data["id"]

    r = await client.get(f"/v1/teach/sessions/{session_id}")
    assert r.status_code == 200
    fetched = r.json()
    assert fetched["name"] == "my-session"


@pytest.mark.asyncio
async def test_create_session_with_seed(client):
    """Create session with seed_experiment_id."""
    r = await client.post(
        "/v1/teach/sessions",
        json={
            "name": "seeded-session",
            "seed_experiment_id": 42,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["seed_experiment_id"] == 42


@pytest.mark.asyncio
async def test_list_sessions(client):
    """GET /teach/sessions returns paginated sessions."""
    for i in range(3):
        await client.post(
            "/v1/teach/sessions",
            json={"name": f"session-{i}"},
        )

    r = await client.get("/v1/teach/sessions")
    assert r.status_code == 200
    data = r.json()
    assert "sessions" in data
    assert len(data["sessions"]) >= 3


@pytest.mark.asyncio
async def test_update_session_status(client):
    """PATCH /teach/sessions/{id}/status updates status."""
    r = await client.post(
        "/v1/teach/sessions",
        json={"name": "status-test"},
    )
    sid = r.json()["id"]

    r = await client.patch(
        f"/v1/teach/sessions/{sid}/status",
        json={"status": TeachingSessionStatus.ACTIVE},
    )
    assert r.status_code == 200
    assert r.json()["status"] == TeachingSessionStatus.ACTIVE


@pytest.mark.asyncio
async def test_delete_session(client):
    """DELETE /teach/sessions/{id} returns 204."""
    r = await client.post(
        "/v1/teach/sessions",
        json={"name": "delete-me"},
    )
    sid = r.json()["id"]

    r = await client.delete(f"/v1/teach/sessions/{sid}")
    assert r.status_code == 204

    r = await client.get(f"/v1/teach/sessions/{sid}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_start_round_rejects_lora(client):
    """POST /teach/sessions/{id}/rounds rejects method != 'full'."""
    r = await client.post(
        "/v1/teach/sessions",
        json={"name": "lora-test"},
    )
    sid = r.json()["id"]

    r = await client.post(
        f"/v1/teach/sessions/{sid}/rounds",
        json={
            "examples": ["hello"],
            "training_config": {"method": "lora"},
        },
    )
    assert r.status_code == 422
    assert "full" in r.json()["detail"]


@pytest.mark.asyncio
async def test_start_round_missing_session(client):
    """POST /teach/sessions/{id}/rounds returns 404 for unknown session."""
    r = await client.post(
        "/v1/teach/sessions/99999/rounds",
        json={
            "examples": ["hello"],
            "training_config": {"method": "full", "num_steps": 5},
        },
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_rounds_for_session(client):
    """GET /teach/sessions/{id}/rounds returns round list."""
    r = await client.post(
        "/v1/teach/sessions",
        json={"name": "round-list-test"},
    )
    sid = r.json()["id"]

    r = await client.get(f"/v1/teach/sessions/{sid}/rounds")
    assert r.status_code == 200
    data = r.json()
    assert "rounds" in data or isinstance(data, list)


@pytest.mark.asyncio
async def test_inspect_round(client):
    """POST /teach/sessions/{id}/rounds/{index}/inspect returns 422 for
    missing experiment.
    """
    r = await client.post(
        "/v1/teach/sessions",
        json={"name": "inspect-test"},
    )
    sid = r.json()["id"]

    r = await client.post(
        f"/v1/teach/sessions/{sid}/rounds/0/inspect",
        json={
            "experiment_id": 99999,
            "prompts": ["hello"],
            "temperature": 0.5,
            "max_tokens": 50,
        },
    )
    # 422 because model not found
    assert r.status_code in (404, 422)


@pytest.mark.asyncio
async def test_compare_rounds(client):
    """POST /teach/sessions/compare returns side-by-side results or error."""
    r = await client.post(
        "/v1/teach/sessions/compare",
        json={
            "left_experiment_id": 1,
            "right_experiment_id": 2,
            "prompts": ["hello"],
        },
    )
    assert r.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_rollback_to_round(client):
    """POST /teach/sessions/{id}/rollback updates chain head."""
    r = await client.post(
        "/v1/teach/sessions",
        json={"name": "rollback-test"},
    )
    sid = r.json()["id"]

    r = await client.post(
        f"/v1/teach/sessions/{sid}/rollback",
        json={"target_experiment_id": 5},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["current_base_experiment_id"] == 5
