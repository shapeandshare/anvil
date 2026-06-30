# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SDK command for triggering an asset download."""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class DownloadAssetsCommand(AbstractCommand):
    """Trigger an async asset download via ``POST /v1/models/{model_id}/download``.

    Returns a ``job_id`` for status polling.
    """

    async def execute(self, model_id: int) -> dict[str, object]:
        """Submit an asset download request for the given model.

        Parameters
        ----------
        model_id : int
            External model primary key.

        Returns
        -------
        dict
            Response with ``job_id`` and ``status`` fields.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.POST,
            f"/v1/models/{model_id}/download",
            response_model=dict,
        )
        return data
