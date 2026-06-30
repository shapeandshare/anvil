# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for tracking service status via the health endpoint.

Tests verify that ``GET /v1/health/detailed`` includes a ``tracking``
block with the correct shape, and that the status reflects the current
state of the ``TrackingService``.

.. note::

   ``app.state.boot_snapshot`` is cleared at module import time
   (below) to prevent stale state from other test files.
"""

from __future__ import annotations

import pytest

from anvil.api.app import app

app.state.boot_snapshot = None
app.state.workspace_paths = None


@pytest.mark.asyncio
async def test_health_detailed_includes_tracking_block(client):
    """GET /v1/health/detailed returns a ``tracking`` block."""
    r = await client.get("/v1/health/detailed")
    assert r.status_code == 200
    data = r.json()
    assert "tracking" in data, "Response missing 'tracking' block"


@pytest.mark.asyncio
async def test_tracking_block_has_correct_shape(client):
    """The ``tracking`` block has the expected fields."""
    r = await client.get("/v1/health/detailed")
    assert r.status_code == 200
    tracking = r.json()["tracking"]

    assert "status" in tracking
    assert "reason" in tracking
    assert "message" in tracking
    assert "last_attempt" in tracking

    assert tracking["status"] in ("active", "degraded")


@pytest.mark.asyncio
async def test_tracking_status_active_by_default(client):
    """Before any MLflow calls, the tracking service reports active."""
    r = await client.get("/v1/health/detailed")
    assert r.status_code == 200
    tracking = r.json()["tracking"]

    # The service hasn't attempted to contact MLflow yet, so it
    # should report active (degraded mode only enters on failure).
    assert tracking["status"] == "active"
    assert tracking["reason"] is None
