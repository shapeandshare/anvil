# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Dataset get command — fetch a single dataset.

``DatasetGetCommand`` retrieves a single dataset by its ID via
``GET /v1/datasets/{id}``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class DatasetGetCommand(AbstractCommand):
    """Get a single dataset — ``GET /v1/datasets/{id}``."""

    async def execute(self, dataset_id: int) -> dict[str, object]:
        """Fetch a single dataset by its primary key.

        Parameters
        ----------
        dataset_id : int
            The dataset's primary key.

        Returns
        -------
        dict[str, object]
            The dataset record as a raw dictionary.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.GET,
            f"/v1/datasets/{dataset_id}",
            response_model=dict,
        )
        return data
