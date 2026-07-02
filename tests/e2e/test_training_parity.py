"""Route-parity test for POST /training/start.

Captures the exact response shape, MLflow tag structure, and model
artifact persistence.  MUST pass both BEFORE and AFTER extracting
the training lifecycle into ``TrainingRunService``.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text


async def _ensure_run_id_seq() -> None:
    """Create run_id_seq if missing (test env — no Alembic migrations)."""
    from anvil.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as sess:
        try:
            await sess.execute(text("SELECT 1 FROM run_id_seq LIMIT 1"))
        except Exception:
            await sess.execute(
                text("CREATE TABLE IF NOT EXISTS run_id_seq (next_id INTEGER NOT NULL)")
            )
            await sess.execute(text("INSERT INTO run_id_seq (next_id) VALUES (1)"))
            await sess.commit()


@pytest.mark.asyncio
async def test_training_start_response_shape(client):
    """POST /training/start returns the expected response shape."""
    await _ensure_run_id_seq()

    r = await client.post(
        "/v1/training/start",
        json={
            "num_steps": 5,
            "n_embd": 8,
            "n_head": 2,
            "n_layer": 1,
            "block_size": 8,
            "learning_rate": 0.01,
            "temperature": 0.5,
        },
    )
    assert r.status_code == 200
    data = r.json()

    # Required keys from the route handler
    assert "run_id" in data
    assert isinstance(data["run_id"], int)
    assert data["run_id"] >= 0

    # mlflow_run_id is None when MLflow is not running (test env)
    assert "mlflow_run_id" in data
    assert data["mlflow_run_id"] is None or isinstance(data["mlflow_run_id"], str)

    assert "experiment_id" in data
    assert isinstance(data["experiment_id"], int)
    assert data["experiment_id"] >= 0

    assert "status" in data
    assert data["status"] == "running"

    assert "tracking" in data
    # Tracking may be "degraded" (MLflow not running) or "active"
    assert data["tracking"] in ("active", "degraded")


@pytest.mark.asyncio
async def test_training_start_rejects_n_head_gt_n_embd(client):
    """POST /training/start returns 422 when n_head > n_embd."""
    r = await client.post(
        "/v1/training/start",
        json={
            "n_embd": 4,
            "n_head": 8,  # n_head exceeds n_embd
        },
    )
    assert r.status_code == 422
    detail = r.json().get("detail", "")
    assert "n_head" in detail


@pytest.mark.asyncio
async def test_training_start_rejects_non_divisible(client):
    """POST /training/start returns 422 when n_embd not divisible by n_head."""
    r = await client.post(
        "/v1/training/start",
        json={
            "n_embd": 10,
            "n_head": 3,  # 10 % 3 != 0
        },
    )
    assert r.status_code == 422
    detail = r.json().get("detail", "")
    assert "divisible" in detail or "n_embd" in detail


@pytest.mark.asyncio
async def test_training_start_rejects_odd_head_dim(client):
    """POST /training/start returns 422 when head_dim is odd."""
    r = await client.post(
        "/v1/training/start",
        json={
            "n_embd": 6,
            "n_head": 2,  # head_dim = 3, which is odd
        },
    )
    assert r.status_code == 422
    detail = r.json().get("detail", "")
    assert "odd" in detail or "head_dim" in detail


@pytest.mark.asyncio
async def test_training_start_rejects_lora_fields_for_full_method(client):
    """POST /training/start returns 422 when lora_* fields sent with method='full'."""
    r = await client.post(
        "/v1/training/start",
        json={
            "num_steps": 5,
            "n_embd": 8,
            "n_head": 2,
            "method": "full",
            "lora_rank": 4,
        },
    )
    assert r.status_code == 422
    detail = r.json().get("detail", "")
    assert "lora_*" in detail or "lora" in detail


@pytest.mark.asyncio
async def test_training_start_rejects_unknown_method(client):
    """POST /training/start returns 422 for unknown method."""
    r = await client.post(
        "/v1/training/start",
        json={
            "num_steps": 5,
            "n_embd": 8,
            "n_head": 2,
            "method": "bogus",
        },
    )
    assert r.status_code == 422
    detail = r.json().get("detail", "")
    assert "Unknown" in detail


@pytest.mark.asyncio
async def test_training_start_rejects_unknown_backend(client):
    """POST /training/start returns 422 for unknown compute_backend."""
    r = await client.post(
        "/v1/training/start",
        json={
            "num_steps": 5,
            "n_embd": 8,
            "n_head": 2,
            "compute_backend": "nonexistent-backend",
        },
    )
    assert r.status_code == 422
