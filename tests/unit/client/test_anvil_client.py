# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the AnvilClient facade — wiring and context manager.

Validates default configuration, custom overrides, API key storage,
sub-client wiring, and context manager idempotency.
"""

from __future__ import annotations

import pytest
from anvil.client.anvil_client import AnvilClient


@pytest.mark.asyncio
async def test_anvil_client_default_config():
    """AnvilClient() uses defaults."""
    ac = AnvilClient()
    assert ac.config.base_url == "http://localhost:8080"
    await ac.aclose()


@pytest.mark.asyncio
async def test_anvil_client_custom_url():
    """AnvilClient(base_url=...) overrides the default."""
    ac = AnvilClient(base_url="http://myhost:9090")
    assert ac.config.base_url == "http://myhost:9090"
    await ac.aclose()


@pytest.mark.asyncio
async def test_anvil_client_with_api_key():
    """AnvilClient(api_key=...) stores the key."""
    ac = AnvilClient(api_key="sk-test")
    assert ac._transport._api_key == "sk-test"
    await ac.aclose()


@pytest.mark.asyncio
async def test_anvil_client_sub_clients_present():
    """Health sub-client is wired after construction."""
    ac = AnvilClient()
    assert ac.health is not None
    await ac.aclose()


@pytest.mark.asyncio
async def test_aclose_works():
    """aclose() can be called without error."""
    ac = AnvilClient()
    await ac.aclose()
    # aclose should be idempotent
    await ac.aclose()