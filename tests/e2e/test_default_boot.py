"""e2e test verifying the default (no-instance-config) boot path
preserves the existing out-of-the-box experience (FR-028, SC-008).

Regression guard: after the feature-028 session/config refactor
(T011/T012), the ``client`` fixture and basic health endpoint must
still work without any workspace configuration.
"""

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """The root health endpoint returns healthy without workspace config."""
    r = await client.get("/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_app_imports():
    """Verify the app module imports without errors in default mode."""
    from anvil.api.app import app

    assert app is not None
