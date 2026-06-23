# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Content stream composition command — stream SSE composition events.

``ContentStreamCompositionCommand`` opens an SSE connection to
``/v1/content/stream/composition`` and yields typed ``StreamEvent``
objects as the server emits composition progress, heartbeats, and
completion signals.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from .._shared.abstract_command import AbstractCommand
from .._shared.stream_event import StreamEvent


class ContentStreamCompositionCommand(AbstractCommand):
    """Stream composition events — ``GET /v1/content/stream/composition``."""

    async def execute(self) -> AsyncIterator[StreamEvent]:
        """Open an SSE stream for content composition and yield events.

        Returns
        -------
        AsyncIterator[StreamEvent]
            An async iterator over typed SSE events from the server
            (progress, heartbeat, completion).
        """
        stream: AsyncIterator[StreamEvent] = self._transport.stream_sse(
            "/v1/content/stream/composition",
        )
        return stream
