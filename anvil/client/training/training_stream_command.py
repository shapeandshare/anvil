# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Training stream command — stream SSE events from a running training run.

``TrainingStreamCommand`` opens an SSE connection to
``/v1/training/stream/{run_id}`` and yields typed ``StreamEvent``
objects as the server emits metrics, heartbeats, and completion signals.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from .._shared.abstract_command import AbstractCommand
from .._shared.stream_event import StreamEvent


class TrainingStreamCommand(AbstractCommand):
    """Stream training events — ``GET /v1/training/stream/{run_id}``."""

    async def execute(self, run_id: str) -> AsyncIterator[StreamEvent]:
        """Open an SSE stream for a training run and yield events.

        Parameters
        ----------
        run_id : str
            The server-assigned run identifier to stream from.

        Returns
        -------
        AsyncIterator[StreamEvent]
            An async iterator over typed SSE events from the server
            (``METRICS``, ``COMPLETE``, ``ERROR``, ``DIVERGENCE``,
            ``HEARTBEAT``, ``EXPORT_ERROR``).
        """
        stream: AsyncIterator[StreamEvent] = self._transport.stream_sse(
            f"/v1/training/stream/{run_id}",
        )
        return stream