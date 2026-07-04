# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the CatalogUnavailableError exception handler.

Tests verify that the FastAPI exception handler translates
``CatalogUnavailableError`` to a ``503`` response with the correct
shape, and that non-catalog routes remain unaffected.
"""

from __future__ import annotations

import json

import pytest
from fastapi import Request
from starlette.responses import JSONResponse

from anvil.api.app import app
from anvil.services.catalog.catalog_unavailable_error import (
    CatalogUnavailableError,
)


def _make_request(path: str) -> Request:
    """Build a minimal Request for testing exception handlers."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 8000),
        "server": ("test", 80),
        "scheme": "http",
        "root_path": "",
        "app": app,
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_catalog_unavailable_handler_is_registered(client):
    """The CatalogUnavailableError handler is registered on the app."""
    handler = app.exception_handlers.get(CatalogUnavailableError)
    assert handler is not None


@pytest.mark.asyncio
async def test_catalog_unavailable_returns_503_shape(client):
    """CatalogUnavailableError returns 503 with CATALOG_UNAVAILABLE code."""
    exc = CatalogUnavailableError("MLflow backend unreachable")
    handler = app.exception_handlers[CatalogUnavailableError]
    request = _make_request("/v1/models")

    response = await handler(request, exc)  # type: ignore[misc]

    assert response.status_code == 503
    body_data = json.loads(bytes(response.body))
    assert body_data["detail"] == "Model catalog unavailable"
    assert body_data["code"] == "CATALOG_UNAVAILABLE"


@pytest.mark.asyncio
async def test_health_unaffected_by_catalog_handler(client):
    """Non-catalog routes like /v1/health remain unaffected."""
    r = await client.get("/v1/health")
    assert r.status_code == 200