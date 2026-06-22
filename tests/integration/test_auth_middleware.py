# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Integration tests for the authentication middleware (spec 017, FR-001/025/027/029).

Exercises the auth gate end-to-end: unauthenticated rejection, API-key and
session-cookie acceptance, exempt routes, OPTIONS preflight bypass, page-route
redirects, and CSRF enforcement on cookie-authenticated mutations.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from anvil.api.app import app
from anvil.api.auth import generate_csrf_token
from anvil.api.deps import get_api_key_store
from anvil.db.base import Base
from anvil.db.session import async_engine

_API_KEY = get_api_key_store().key or ""


@pytest.fixture
async def unauth_client():
    """Async client with NO auth credentials and a clean schema."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as ac:
        yield ac
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_unauthenticated_api_request_returns_401(unauth_client):
    resp = await unauth_client.get("/v1/compute/backends")
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_valid_api_key_grants_access(unauth_client):
    resp = await unauth_client.get(
        "/v1/compute/backends", headers={"X-API-Key": _API_KEY}
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_wrong_api_key_rejected(unauth_client):
    resp = await unauth_client.get(
        "/v1/compute/backends", headers={"X-API-Key": "wrong-key-value"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_health_endpoint_is_exempt(unauth_client):
    resp = await unauth_client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_login_page_is_exempt(unauth_client):
    resp = await unauth_client.get("/login")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_unauthenticated_page_route_redirects_to_login(unauth_client):
    resp = await unauth_client.get(
        "/", headers={"accept": "text/html"}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_options_preflight_bypasses_auth(unauth_client):
    resp = await unauth_client.options("/v1/compute/backends")
    assert resp.status_code != 401


@pytest.mark.asyncio
async def test_session_cookie_grants_access(unauth_client):
    login = await unauth_client.post("/login", json={"api_key": _API_KEY})
    assert login.status_code == 200
    resp = await unauth_client.get("/v1/compute/backends")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_invalid_login_returns_401(unauth_client):
    resp = await unauth_client.post("/login", json={"api_key": "nope"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_security_headers_present(unauth_client):
    resp = await unauth_client.get("/v1/health")
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in resp.headers
    assert "Strict-Transport-Security" in resp.headers


@pytest.mark.asyncio
async def test_cookie_auth_post_without_csrf_rejected(unauth_client):
    await unauth_client.post("/login", json={"api_key": _API_KEY})
    resp = await unauth_client.post("/v1/datasets", json={"name": "csrf-test"})
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_cookie_auth_post_with_csrf_accepted(unauth_client):
    login = await unauth_client.post("/login", json={"api_key": _API_KEY})
    session_id = login.json()["session_id"]
    csrf = generate_csrf_token(session_id)
    resp = await unauth_client.post(
        "/v1/datasets",
        json={"name": "csrf-ok"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_key_auth_exempt_from_csrf(unauth_client):
    resp = await unauth_client.post(
        "/v1/datasets",
        json={"name": "apikey-nocsrf"},
        headers={"X-API-Key": _API_KEY},
    )
    assert resp.status_code == 200
