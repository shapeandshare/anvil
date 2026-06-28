# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for runtime config CRUD API endpoints (User Story 2).

Tests assume the ``client`` fixture (from ``tests/conftest.py``) is
available.  The in-memory SQLite database is used so the runtime_config
table is auto-created by ``Base.metadata.create_all``.

.. note::

   ``app.state.boot_snapshot`` is cleared at module import time
   (below) so that pending-restart comparisons use the fallback
   logic rather than stale values left by other test files that
   run in the same process.
"""

from __future__ import annotations

import pytest

# Clear cross-test contamination: other test files (isolation,
# lifecycle) may have set ``app.state.boot_snapshot`` from their
# lifespan.  This reset ensures pending-restart falls back to the
# safe "any non-live override is pending" logic.
from anvil.api.app import app

app.state.boot_snapshot = None
app.state.workspace_paths = None


@pytest.mark.asyncio
async def test_list_config_returns_all_settings(client):
    """GET /v1/config returns the full catalog as a list."""
    r = await client.get("/v1/config")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    entry = data[0]
    assert "key" in entry
    assert "value" in entry
    assert "source" in entry
    assert "apply_class" in entry
    assert "pending_restart" in entry
    assert "editable" in entry


@pytest.mark.asyncio
async def test_get_config_by_key(client):
    """GET /v1/config/{key} returns a single setting."""
    r = await client.get("/v1/config/device")
    assert r.status_code == 200
    data = r.json()
    assert data["key"] == "device"
    assert data["apply_class"] in ("boot_critical", "mlflow_restart", "applies_live")


@pytest.mark.asyncio
async def test_get_config_not_found(client):
    """GET /v1/config/{key} returns 404 for unknown keys."""
    r = await client.get("/v1/config/nonexistent_key_xyz")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_config_override(client):
    """PUT /v1/config/{key} persists an override and returns updated value."""
    r = await client.put(
        "/v1/config/device",
        json={"value": "cpu"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["key"] == "device"
    assert data["value"] == "cpu"
    assert data["source"] == "override"

    # Verify the override is persisted on re-read.
    r2 = await client.get("/v1/config/device")
    assert r2.status_code == 200
    assert r2.json()["value"] == "cpu"


@pytest.mark.asyncio
async def test_update_config_unknown_key(client):
    """PUT /v1/config/{key} returns 400 for unknown keys."""
    r = await client.put(
        "/v1/config/nonexistent_key_xyz",
        json={"value": "test"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_reset_config_override(client):
    """POST /v1/config/{key}/reset removes an override and reverts."""
    # First set an override.
    await client.put("/v1/config/device", json={"value": "cpu"})

    # Then reset it.
    r = await client.post("/v1/config/device/reset")
    assert r.status_code == 200
    data = r.json()
    assert data["key"] == "device"
    assert data["source"] in ("env", "default")
    assert data["value"] != "override"


@pytest.mark.asyncio
async def test_reset_config_unknown_key(client):
    """POST /v1/config/{key}/reset returns 400 for unknown keys."""
    r = await client.post("/v1/config/nonexistent_key_xyz/reset")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_config_page_renders(client):
    """GET /v1/config-page returns HTML."""
    r = await client.get("/v1/config-page")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_update_config_extra_fields_rejected(client):
    """PUT /v1/config/{key} rejects extra fields (extra='forbid')."""
    r = await client.put(
        "/v1/config/device",
        json={"value": "cpu", "extra_field": "should_fail"},
    )
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_get_config_has_expected_keys(client):
    """GET /v1/config returns known settings from the catalog."""
    r = await client.get("/v1/config")
    assert r.status_code == 200
    keys = {s["key"] for s in r.json()}
    assert "device" in keys
    assert "port" in keys
    assert "mlflow_uri" in keys
    assert "log_dir" in keys
    assert "backup_quota_bytes" in keys


@pytest.mark.asyncio
async def test_config_pending_restart_flag(client):
    """Setting a boot_critical key marks pending_restart=True."""
    r = await client.put("/v1/config/port", json={"value": "9090"})
    assert r.status_code == 200
    data = r.json()
    assert data["apply_class"] == "boot_critical"
    assert data["pending_restart"] is True


@pytest.mark.asyncio
async def test_config_applies_live_no_pending(client):
    """Setting an applies_live key keeps pending_restart=False."""
    r = await client.put("/v1/config/device", json={"value": "mps"})
    assert r.status_code == 200
    data = r.json()
    assert data["apply_class"] == "applies_live"
    assert data["pending_restart"] is False


# ── T048: MLflow auto-restart and boot-critical pending status ────────


@pytest.mark.asyncio
async def test_mlflow_restart_pending_flag(client):
    """Setting an MLFLOW_RESTART key marks pending_restart=True."""
    r = await client.put(
        "/v1/config/mlflow_uri", json={"value": "http://127.0.0.1:9999"}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["apply_class"] == "mlflow_restart"
    assert data["pending_restart"] is True


@pytest.mark.asyncio
async def test_mlflow_restart_auto_restart_no_crash(client):
    """PUT on mlflow_restart key does not crash when MLflow is None."""
    r = await client.put(
        "/v1/config/mlflow_uri", json={"value": "http://127.0.0.1:8888"}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["key"] == "mlflow_uri"
    assert data["value"] == "http://127.0.0.1:8888"
    assert data["apply_class"] == "mlflow_restart"


@pytest.mark.asyncio
async def test_pending_restart_endpoint(client):
    """GET /v1/config/pending-restart returns only pending settings."""
    # Set a boot_critical override to create a pending item.
    await client.put("/v1/config/port", json={"value": "7070"})
    r = await client.get("/v1/config/pending-restart")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    keys = {s["key"] for s in data}
    assert "port" in keys
    # applies_live keys should NOT appear in pending-restart.
    assert "device" not in keys
    assert "backup_quota_bytes" not in keys
    for s in data:
        assert s["pending_restart"] is True


@pytest.mark.asyncio
async def test_pending_restart_cleared_on_reset(client):
    """After resetting a pending override, pending_restart becomes False."""
    await client.put("/v1/config/port", json={"value": "6060"})
    r_check = await client.get("/v1/config/pending-restart")
    assert r_check.status_code == 200
    pre_keys = {s["key"] for s in r_check.json()}
    assert "port" in pre_keys

    await client.post("/v1/config/port/reset")
    r_after = await client.get("/v1/config/pending-restart")
    assert r_after.status_code == 200
    post_keys = {s["key"] for s in r_after.json()}
    assert "port" not in post_keys
