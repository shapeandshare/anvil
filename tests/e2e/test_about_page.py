"""e2e tests for the /v1/about page.

Verifies that the about page returns a 200 status code with
HTML content, and that the health/detailed endpoint remains
backward compatible.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_about_page_returns_200(client) -> None:
    """Test that the about page returns a 200 status with HTML content.

    The about page is a Jinja2-rendered HTML page with license
    catalog and environment snapshot context.
    """
    r = await client.get("/v1/about")
    assert r.status_code == 200
    # Must return HTML (not JSON)
    assert "text/html" in r.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_health_detailed_backward_compatible(client) -> None:
    """Test that the health/detailed endpoint JSON shape is unchanged.

    This ensures the shared-helper extraction does not alter the
    response contract for any existing consumers.
    """
    r = await client.get("/v1/health/detailed")
    assert r.status_code == 200
    data = r.json()
    # Core health fields must still be present
    assert data["status"] == "healthy"
    assert "version" in data
    assert "uptime_seconds" in data
    assert "system" in data
    assert "gpu" in data
    assert "database" in data
    assert "mlflow" in data
    assert "tracking" in data
    assert "docs" in data
