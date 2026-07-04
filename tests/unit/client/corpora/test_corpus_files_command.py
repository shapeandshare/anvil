# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for CorpusFilesCommand — GET with optional language filter."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.corpora.corpus_files_command import CorpusFilesCommand


class TestCorpusFilesCommand:
    """CorpusFilesCommand: GET /v1/corpora/{id}/files[?language=]."""

    @pytest.mark.asyncio
    async def test_execute_without_language(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=[])
        cmd = CorpusFilesCommand(transport)
        result = await cmd.execute(corpus_id=1)
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/corpora/1/files"
        assert kwargs.get("params") is None

    @pytest.mark.asyncio
    async def test_execute_with_language(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=[{"path": "f.py"}])
        cmd = CorpusFilesCommand(transport)
        result = await cmd.execute(corpus_id=1, language="python")
        _, kwargs = transport.request.call_args
        assert kwargs["params"] == {"language": "python"}

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = [{"path": "f.py"}, {"path": "f.md"}]
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = CorpusFilesCommand(transport)
        result = await cmd.execute(corpus_id=1)
        assert result == expected
