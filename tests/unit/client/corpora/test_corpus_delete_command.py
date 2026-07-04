# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for CorpusDeleteCommand — DELETE with required corpus_id."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.corpora.corpus_delete_command import CorpusDeleteCommand


class TestCorpusDeleteCommand:
    """CorpusDeleteCommand: DELETE /v1/corpora/{id}."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_delete(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"deleted": True})
        cmd = CorpusDeleteCommand(transport)
        result = await cmd.execute(corpus_id=1)
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.DELETE
        assert args[1] == "/v1/corpora/1"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"deleted": True}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = CorpusDeleteCommand(transport)
        result = await cmd.execute(corpus_id=1)
        assert result == expected
