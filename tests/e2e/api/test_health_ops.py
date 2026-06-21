# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the health and operations router."""

import pytest


@pytest.mark.asyncio
async def test_health(client):
    """GET /v1/health returns status healthy with system and GPU info."""
    r = await client.get("/v1/health")
    assert r.status_code == 200

    data = r.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "uptime_seconds" in data
    assert "system" in data
    assert "gpu" in data


@pytest.mark.asyncio
async def test_services(client):
    """GET /v1/services returns a list of services with web and mlflow."""
    r = await client.get("/v1/services")
    assert r.status_code == 200

    data = r.json()
    services = data["services"]
    assert isinstance(services, list)

    web = next(s for s in services if s["name"] == "web")
    assert web["status"] == "running"

    mlflow = next(s for s in services if s["name"] == "mlflow")
    assert mlflow["status"] in ("running", "stopped", "external")
    assert isinstance(mlflow.get("port"), int)
    assert isinstance(mlflow.get("mlflow_url"), str)


@pytest.mark.asyncio
async def test_demo_bootstrap_idempotent(client):
    """POST /v1/demo/bootstrap is idempotent — second call skips existing."""
    r1 = await client.post("/v1/demo/bootstrap")
    assert r1.status_code == 200

    result1 = r1.json()
    assert "corpora_created" in result1
    assert "datasets_created" in result1
    assert "corpora_skipped" in result1
    assert "datasets_skipped" in result1
    assert "errors" in result1
    assert "total_time_ms" in result1

    r2 = await client.post("/v1/demo/bootstrap")
    assert r2.status_code == 200

    result2 = r2.json()
    assert result2["corpora_created"] == 0
    assert result2["corpora_skipped"] > 0


@pytest.mark.asyncio
async def test_service_control_safe(client):
    """Service control endpoints respond without destabilizing the process."""
    r = await client.get("/v1/services")
    assert r.status_code == 200
    data = r.json()
    assert "services" in data
    assert isinstance(data["services"], list)

    r2 = await client.post("/v1/services/restart-all")
    assert r2.status_code < 500
