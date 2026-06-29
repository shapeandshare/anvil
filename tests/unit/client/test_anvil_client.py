# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the AnvilClient facade — wiring, config, auth, and context
manager.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from anvil.client._shared.server_config import ServerConfig
from anvil.client._shared.transport import Transport
from anvil.client.anvil_client import AnvilClient

####################################################################
# Sub-client types (for isinstance checks)
####################################################################

from anvil.client.compute.compute_client import ComputeClient
from anvil.client.content.content_client import ContentClient
from anvil.client.corpora.corpora_client import CorporaClient
from anvil.client.datasets.datasets_client import DatasetsClient
from anvil.client.eval.eval_client import EvalClient
from anvil.client.experiments.experiments_client import ExperimentsClient
from anvil.client.governance.governance_client import GovernanceClient
from anvil.client.health.health_client import HealthClient
from anvil.client.inference.inference_client import InferenceClient
from anvil.client.models.models_client import ModelsClient
from anvil.client.registry.registry_client import RegistryClient
from anvil.client.services.services_client import ServicesClient
from anvil.client.training.training_client import TrainingClient


####################################################################
# Initialization
####################################################################


class TestInit:
    """AnvilClient construction and default resolution."""

    @pytest.mark.asyncio
    async def test_default_config(self) -> None:
        ac = AnvilClient()
        assert ac.config.base_url == "http://localhost:8080"
        assert ac.config.timeout == 30.0
        assert ac.config.retry_count == 3
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_custom_base_url(self) -> None:
        ac = AnvilClient(base_url="http://myhost:9090")
        assert ac.config.base_url == "http://myhost:9090"
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_custom_timeout(self) -> None:
        ac = AnvilClient(timeout=60.0)
        assert ac.config.timeout == 60.0
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_custom_retry_count(self) -> None:
        ac = AnvilClient(retry_count=5)
        assert ac.config.retry_count == 5
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_with_api_key(self) -> None:
        ac = AnvilClient(api_key="sk-test")
        assert ac._transport._api_key == "sk-test"
        assert ac._transport._auth_mode == "api_key"
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_without_api_key(self) -> None:
        ac = AnvilClient()
        assert ac._transport._api_key is None
        assert ac._transport._auth_mode == "none"
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_config_object_overrides_everything(self) -> None:
        cfg = ServerConfig(base_url="http://override:1111", timeout=99.0, retry_count=0)
        ac = AnvilClient(
            base_url="http://ignored:2222",
            timeout=1.0,
            retry_count=99,
            config=cfg,
        )
        assert ac.config.base_url == "http://override:1111"
        assert ac.config.timeout == 99.0
        assert ac.config.retry_count == 0
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_custom_http_client_injected(self) -> None:
        custom = httpx.AsyncClient()
        ac = AnvilClient(_client=custom)
        assert ac._transport._client is custom
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_config_property_readback(self) -> None:
        ac = AnvilClient()
        assert isinstance(ac.config, ServerConfig)
        await ac.aclose()


####################################################################
# Sub-client properties
####################################################################


class TestSubClients:
    """All 13 domain sub-client properties wire correctly."""

    @pytest.mark.asyncio
    async def test_health(self) -> None:
        ac = AnvilClient()
        assert isinstance(ac.health, HealthClient)
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_datasets(self) -> None:
        ac = AnvilClient()
        assert isinstance(ac.datasets, DatasetsClient)
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_training(self) -> None:
        ac = AnvilClient()
        assert isinstance(ac.training, TrainingClient)
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_experiments(self) -> None:
        ac = AnvilClient()
        assert isinstance(ac.experiments, ExperimentsClient)
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_inference(self) -> None:
        ac = AnvilClient()
        assert isinstance(ac.inference, InferenceClient)
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_registry(self) -> None:
        ac = AnvilClient()
        assert isinstance(ac.registry, RegistryClient)
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_corpora(self) -> None:
        ac = AnvilClient()
        assert isinstance(ac.corpora, CorporaClient)
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_eval(self) -> None:
        ac = AnvilClient()
        assert isinstance(ac.eval, EvalClient)
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_compute(self) -> None:
        ac = AnvilClient()
        assert isinstance(ac.compute, ComputeClient)
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_services(self) -> None:
        ac = AnvilClient()
        assert isinstance(ac.services, ServicesClient)
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_governance(self) -> None:
        ac = AnvilClient()
        assert isinstance(ac.governance, GovernanceClient)
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_content(self) -> None:
        ac = AnvilClient()
        assert isinstance(ac.content, ContentClient)
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_models(self) -> None:
        ac = AnvilClient()
        assert isinstance(ac.models, ModelsClient)
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_sub_clients_are_cached(self) -> None:
        """Accessing the same property twice returns the same instance."""
        ac = AnvilClient()
        h1 = ac.health
        h2 = ac.health
        assert h1 is h2
        await ac.aclose()


####################################################################
# Auth — login / logout
####################################################################


class TestAuth:
    """login() and logout() delegation."""

    @pytest.mark.asyncio
    async def test_login_sends_api_key_and_switches_auth_mode(self) -> None:
        ac = AnvilClient()
        ac._transport.request = AsyncMock(return_value={})

        await ac.login("sk-session")

        ac._transport.request.assert_called_once()
        call_args = ac._transport.request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/login"
        assert call_args[1].get("json") == {"api_key": "sk-session"}
        assert ac._transport._auth_mode == "session"
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_logout_calls_post_logout_and_resets_auth(self) -> None:
        ac = AnvilClient()
        ac._transport.request = AsyncMock(return_value={})
        ac._transport._auth_mode = "session"

        await ac.logout()

        ac._transport.request.assert_called_once()
        call_args = ac._transport.request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/logout"
        assert ac._transport._auth_mode == "none"
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_login_auth_mode_not_session_on_failure(self) -> None:
        """If login request raises, auth mode should remain unchanged."""
        ac = AnvilClient()
        ac._transport.request = AsyncMock(side_effect=RuntimeError("fail"))

        with pytest.raises(RuntimeError):
            await ac.login("sk-bad")

        assert ac._transport._auth_mode != "session"
        await ac.aclose()


####################################################################
# Context manager
####################################################################


class TestContextManager:
    """Async context manager (async with)."""

    @pytest.mark.asyncio
    async def test_aenter_returns_self(self) -> None:
        ac = AnvilClient()
        result = await ac.__aenter__()
        assert result is ac
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_aexit_closes_transport(self) -> None:
        ac = AnvilClient()
        ac._transport.aclose = AsyncMock()
        await ac.__aexit__(None, None, None)
        ac._transport.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_with_block(self) -> None:
        """Using ``async with AnvilClient() as ac:`` closes transport after the block."""
        original_close = AsyncMock()
        # We need an AnvilClient where aclose is mocked
        # Use a custom scenario: patch transport aclose
        ac = AnvilClient()
        ac._transport.aclose = original_close

        async with ac as client:
            assert client is ac

        original_close.assert_called_once()


####################################################################
# Lifecycle
####################################################################


class TestLifecycle:
    """aclose idempotency and resource cleanup."""

    @pytest.mark.asyncio
    async def test_aclose_idempotent(self) -> None:
        ac = AnvilClient()
        # First call should work
        await ac.aclose()
        # Second call should also work (idempotent)
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_aclose_delegates_to_transport(self) -> None:
        ac = AnvilClient()
        ac._transport.aclose = AsyncMock()
        await ac.aclose()
        ac._transport.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_config_readable_after_close(self) -> None:
        ac = AnvilClient()
        await ac.aclose()
        # Config should still be readable after close
        assert ac.config.base_url == "http://localhost:8080"