# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for per-user secrets API endpoints.

Tests assume the ``client`` fixture (from ``tests/conftest.py``) is
available.  The in-memory SQLite database is used so all required
tables are auto-created by ``Base.metadata.create_all``.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_secrets_returns_data_key(client):
    """GET /v1/user/secrets returns 200 with a ``data`` key."""
    r = await client.get("/v1/user/secrets")
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert isinstance(body["data"], list)


@pytest.mark.asyncio
async def test_set_secret_creates_secret(client):
    """POST /v1/user/secrets creates a secret and returns 201."""
    r = await client.post(
        "/v1/user/secrets",
        json={"key": "test_key", "value": "test_value"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body == {"status": "created"}

    # Verify the secret appears in the listing.
    r2 = await client.get("/v1/user/secrets")
    assert r2.status_code == 200
    keys = r2.json()["data"]
    assert "test_key" in keys


@pytest.mark.asyncio
async def test_delete_secret_removes_secret(client):
    """DELETE /v1/user/secrets deletes a secret and returns 200."""
    # First create a secret.
    await client.post(
        "/v1/user/secrets",
        json={"key": "delete_me", "value": "to_be_removed"},
    )

    # Delete it.
    r = await client.delete("/v1/user/secrets", params={"key": "delete_me"})
    assert r.status_code == 200
    body = r.json()
    assert body == {"status": "deleted"}

    # Verify it no longer appears in the listing.
    r2 = await client.get("/v1/user/secrets")
    assert r2.status_code == 200
    keys = r2.json()["data"]
    assert "delete_me" not in keys
