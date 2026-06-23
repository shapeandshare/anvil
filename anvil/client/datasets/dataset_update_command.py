# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Dataset update command — update an existing dataset.

``DatasetUpdateCommand`` updates a dataset's fields on the server via
``PUT /v1/datasets/{id}``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class DatasetUpdateCommand(AbstractCommand):
    """Update a dataset — ``PUT /v1/datasets/{id}``."""

    async def execute(
        self,
        dataset_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> dict[str, object]:
        """Update an existing dataset's fields.

        Parameters
        ----------
        dataset_id : int
            The dataset's primary key.
        name : str | None, optional
            New name for the dataset. Omit to leave unchanged.
        description : str | None, optional
            New description for the dataset. Omit to leave unchanged.

        Returns
        -------
        dict[str, object]
            The updated dataset record as a raw dictionary.
        """
        body: dict[str, object] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        data: dict[str, object] = await self._transport.request(
            HttpMethod.PUT,
            f"/v1/datasets/{dataset_id}",
            json=body,
            response_model=dict,
        )
        return data
