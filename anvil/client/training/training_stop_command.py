# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Training stop command — stop a running training run.

``TrainingStopCommand`` sends a ``POST /v1/training/{run_id}/stop``
request and returns the server's confirmation payload.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class TrainingStopCommand(AbstractCommand):
    """Stop a training run — ``POST /v1/training/{run_id}/stop``."""

    async def execute(self, run_id: str) -> dict[str, object]:
        """Request the server to stop a running training run.

        Parameters
        ----------
        run_id : str
            The server-assigned run identifier to stop.

        Returns
        -------
        dict[str, object]
            Confirmation payload.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.POST,
            f"/v1/training/{run_id}/stop",
            response_model=dict,
        )
        return data
