# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Dataset create command — create a new dataset.

``DatasetCreateCommand`` creates a new dataset on the server via
``POST /v1/datasets``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class DatasetCreateCommand(AbstractCommand):
    """Create a new dataset — ``POST /v1/datasets``."""

    async def execute(
        self, name: str, description: str | None = None,
    ) -> dict[str, object]:
        """Create a new dataset on the server.

        Parameters
        ----------
        name : str
            The dataset name.
        description : str | None, optional
            An optional description for the dataset.

        Returns
        -------
        dict[str, object]
            The newly created dataset record as a raw dictionary.
        """
        body: dict[str, object] = {"name": name}
        if description is not None:
            body["description"] = description
        data: dict[str, object] = await self._transport.request(
            HttpMethod.POST, "/v1/datasets", json=body, response_model=dict,
        )
        return data
