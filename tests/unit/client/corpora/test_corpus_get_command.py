# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for CorpusGetCommand — GET with required corpus_id."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.corpora.corpus_get_command import CorpusGetCommand


class TestCorpusGetCommand:
    """CorpusGetCommand: GET /v1/corpora/{id}."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"id": 1})
        cmd = CorpusGetCommand(transport)
        result = await cmd.execute(corpus_id=42)
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/corpora/42"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"id": 42, "name": "test"}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = CorpusGetCommand(transport)
        result = await cmd.execute(corpus_id=42)
        assert result == expected
