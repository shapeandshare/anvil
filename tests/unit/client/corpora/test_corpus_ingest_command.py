# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for CorpusIngestCommand — POST with optional max_files."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.corpora.corpus_ingest_command import CorpusIngestCommand


class TestCorpusIngestCommand:
    """CorpusIngestCommand: POST /v1/corpora/{id}/ingest[?max_files=]."""

    @pytest.mark.asyncio
    async def test_execute_without_max_files(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"status": "ok"})
        cmd = CorpusIngestCommand(transport)
        result = await cmd.execute(corpus_id=1)
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.POST
        assert args[1] == "/v1/corpora/1/ingest"
        assert kwargs.get("params") is None

    @pytest.mark.asyncio
    async def test_execute_with_max_files(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"status": "ok"})
        cmd = CorpusIngestCommand(transport)
        result = await cmd.execute(corpus_id=1, max_files=10)
        _, kwargs = transport.request.call_args
        assert kwargs["params"] == {"max_files": "10"}

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"status": "ok", "files_ingested": 5}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = CorpusIngestCommand(transport)
        result = await cmd.execute(corpus_id=1)
        assert result == expected
