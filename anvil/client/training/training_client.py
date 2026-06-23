# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Training client — domain aggregator for training lifecycle operations.

``TrainingClient`` provides a single entry point for all training
operations: start, status, stop, and SSE stream. It delegates each
operation to its corresponding command class.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from .._shared.stream_event import StreamEvent
from .._shared.transport import Transport
from .training_config import TrainingConfig
from .training_start_command import TrainingStartCommand
from .training_status_command import TrainingStatusCommand
from .training_stop_command import TrainingStopCommand
from .training_stream_command import TrainingStreamCommand


class TrainingClient:
    """Training lifecycle operations.

    Aggregates all training commands behind a single facade. Each public
    method maps to one server API operation.

    Parameters
    ----------
    transport : Transport
        The shared SDK transport instance.
    """

    def __init__(self, transport: Transport) -> None:
        self._start = TrainingStartCommand(transport)
        self._status = TrainingStatusCommand(transport)
        self._stop = TrainingStopCommand(transport)
        self._stream = TrainingStreamCommand(transport)

    async def start(self, config: TrainingConfig) -> dict[str, object]:
        """Start a new training run.

        Parameters
        ----------
        config : TrainingConfig
            Hyperparameters and data-source references.

        Returns
        -------
        dict[str, object]
            The server response with ``run_id``, ``mlflow_run_id``, and
            ``experiment_id``.
        """
        return await self._start.execute(config)

    async def status(self, run_id: str) -> dict[str, object]:
        """Query the status of a training run.

        Parameters
        ----------
        run_id : str
            The server-assigned run identifier.

        Returns
        -------
        dict[str, object]
            Status payload.
        """
        return await self._status.execute(run_id)

    async def stop(self, run_id: str) -> dict[str, object]:
        """Stop a running training run.

        Parameters
        ----------
        run_id : str
            The server-assigned run identifier to stop.

        Returns
        -------
        dict[str, object]
            Confirmation payload.
        """
        return await self._stop.execute(run_id)

    async def stream(self, run_id: str) -> AsyncIterator[StreamEvent]:
        """Stream SSE events from a running training run.

        Parameters
        ----------
        run_id : str
            The server-assigned run identifier to stream from.

        Yields
        ------
        StreamEvent
            Typed SSE events from the server.
        """
        async for event in await self._stream.execute(run_id):
            yield event
