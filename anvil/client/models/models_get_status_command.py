# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SDK command for polling an import job status."""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ModelsGetStatusCommand(AbstractCommand):
    """Poll import job status via ``GET /v1/models/import/{job_id}/status``."""

    async def execute(self, job_id: int) -> dict[str, object]:
        """Return the current job status.

        Parameters
        ----------
        job_id : int
            Import job ID from ``import_model()``.

        Returns
        -------
        dict
            Job status response with ``status``, ``error_code``,
            ``error_message``, ``external_model_id``.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.GET,
            f"/v1/models/import/{job_id}/status",
            response_model=dict,
        )
        return data
