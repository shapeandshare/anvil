# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ContentStreamCompositionCommand — no-arg SSE stream."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import MagicMock

import pytest

from anvil.client.content.content_stream_composition_command import (
    ContentStreamCompositionCommand,
)


class TestContentStreamCompositionCommand:
    """ContentStreamCompositionCommand: GET /v1/content/stream/composition."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_stream_sse(self) -> None:
        transport = MagicMock()
        transport.stream_sse = MagicMock(return_value=MagicMock(spec=AsyncIterator))
        cmd = ContentStreamCompositionCommand(transport)
        result = await cmd.execute()
        transport.stream_sse.assert_called_once_with(
            "/v1/content/stream/composition",
        )

    @pytest.mark.asyncio
    async def test_execute_returns_transport_stream(self) -> None:
        expected = MagicMock(spec=AsyncIterator)
        transport = MagicMock()
        transport.stream_sse = MagicMock(return_value=expected)
        cmd = ContentStreamCompositionCommand(transport)
        result = await cmd.execute()
        assert result is expected
