# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for GET /v1/compute/backends route."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from anvil.api.app import app


@pytest.mark.asyncio
async def test_compute_backends_returns_json_array():
    """GET /v1/compute/backends returns a JSON array of backend dicts."""
    fake_backends = [
        {"value": "auto", "label": "Auto", "available": True, "reason": None},
        {
            "value": "local-cpu",
            "label": "Local (CPU)",
            "available": True,
            "reason": None,
        },
        {
            "value": "local-gpu",
            "label": "Local (GPU)",
            "available": False,
            "reason": "No GPU detected",
        },
        {
            "value": "modal",
            "label": "Modal (cloud GPU)",
            "available": False,
            "reason": "modal package not installed",
        },
    ]
    with patch("anvil.api.v1.compute.available_backends", return_value=fake_backends):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/compute/backends")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 4
            for entry in data:
                assert "value" in entry
                assert "label" in entry
                assert "available" in entry
                assert isinstance(entry["available"], bool)


@pytest.mark.asyncio
async def test_compute_backends_unavailable_include_reason():
    """Unavailable backends include a 'reason' field."""
    fake_backends = [
        {"value": "auto", "label": "Auto", "available": True, "reason": None},
        {
            "value": "local-gpu",
            "label": "Local (GPU)",
            "available": False,
            "reason": "No GPU detected",
        },
        {
            "value": "modal",
            "label": "Modal (cloud GPU)",
            "available": False,
            "reason": "modal package not installed",
        },
    ]
    with patch("anvil.api.v1.compute.available_backends", return_value=fake_backends):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/compute/backends")
            assert response.status_code == 200
            data = response.json()
            for entry in data:
                if not entry["available"]:
                    assert "reason" in entry
                    assert isinstance(entry["reason"], str)
                    assert len(entry["reason"]) > 0
                else:
                    assert entry["reason"] is None


@pytest.mark.asyncio
async def test_compute_backends_empty_registry():
    """GET /v1/compute/backends returns empty list when no backends registered."""
    with patch("anvil.api.v1.compute.available_backends", return_value=[]):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/compute/backends")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 0
