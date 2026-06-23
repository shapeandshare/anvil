# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Training status command — query the current status of a training run.

``TrainingStatusCommand`` sends a ``GET /v1/training/{run_id}/status``
request and returns the server's status payload.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class TrainingStatusCommand(AbstractCommand):
    """Query training run status — ``GET /v1/training/{run_id}/status``."""

    async def execute(self, run_id: str) -> dict[str, object]:
        """Fetch the current status of a training run.

        Parameters
        ----------
        run_id : str
            The server-assigned run identifier.

        Returns
        -------
        dict[str, object]
            Status payload with fields such as ``status``, ``step``,
            ``loss``, and ``elapsed_seconds``.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.GET,
            f"/v1/training/{run_id}/status",
            response_model=dict,
        )
        return data
