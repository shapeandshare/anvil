# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Shared test helpers for authenticated API test clients."""

from httpx import ASGITransport, AsyncClient

from anvil.api.app import app
from anvil.api.deps import get_api_key_store

TEST_API_KEY = get_api_key_store().key or ""


def authed_client() -> AsyncClient:
    """Create an ``httpx.AsyncClient`` with the test API key pre-injected.

    Returns
    -------
    AsyncClient
        An asynchronous test client authenticated as the local user.
    """
    transport = ASGITransport(app=app)
    return AsyncClient(
        transport=transport,
        base_url="https://test",
        headers={"X-API-Key": TEST_API_KEY},
    )
