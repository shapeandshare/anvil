# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SDK command for polling an asset download job status."""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class DownloadStatusCommand(AbstractCommand):
    """Poll asset download job status via
    ``GET /v1/models/{model_id}/download/{job_id}/status``.
    """

    async def execute(self, model_id: int, job_id: int) -> dict[str, object]:
        """Return the current download job status with progress.

        Parameters
        ----------
        model_id : int
            External model primary key.
        job_id : int
            Download job ID from ``download_assets()``.

        Returns
        -------
        dict
            Job status with ``status``, ``total_assets``,
            ``completed_assets``, and per-asset detail.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.GET,
            f"/v1/models/{model_id}/download/{job_id}/status",
            response_model=dict,
        )
        return data
