# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SDK command for retrieving a single external model."""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ModelsGetCommand(AbstractCommand):
    """Retrieve an external model via ``GET /v1/models/external/{model_id}``."""

    async def execute(self, model_id: int) -> dict[str, object]:
        """Return a single external model by ID.

        Parameters
        ----------
        model_id : int
            External model primary key.

        Returns
        -------
        dict
            Model metadata response.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.GET,
            f"/v1/models/external/{model_id}",
            response_model=dict,
        )
        return data