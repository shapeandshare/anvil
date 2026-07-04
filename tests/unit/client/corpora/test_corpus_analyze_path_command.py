# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for CorpusAnalyzePathCommand — POST with path body."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.corpora.corpus_analyze_path_command import CorpusAnalyzePathCommand


class TestCorpusAnalyzePathCommand:
    """CorpusAnalyzePathCommand: POST /v1/corpora/analyze-path."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_post(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"files": []})
        cmd = CorpusAnalyzePathCommand(transport)
        result = await cmd.execute(path="/some/dir")
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.POST
        assert args[1] == "/v1/corpora/analyze-path"
        assert kwargs["json"] == {"path": "/some/dir"}

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"files": [{"path": "f.py"}]}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = CorpusAnalyzePathCommand(transport)
        result = await cmd.execute(path="/p")
        assert result == expected
