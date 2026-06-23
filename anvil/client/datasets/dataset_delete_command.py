# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Dataset delete command — delete a dataset.

``DatasetDeleteCommand`` removes a dataset from the server via
``DELETE /v1/datasets/{id}[?force=]``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class DatasetDeleteCommand(AbstractCommand):
    """Delete a dataset — ``DELETE /v1/datasets/{id}[?force=]``."""

    async def execute(
        self,
        dataset_id: int,
        *,
        force: bool = False,
    ) -> dict[str, object]:
        """Delete a dataset from the server.

        Parameters
        ----------
        dataset_id : int
            The dataset's primary key.
        force : bool, optional
            If ``True``, force deletion even if the dataset has associated
            resources. Defaults to ``False``.

        Returns
        -------
        dict[str, object]
            A response payload confirming the deletion.
        """
        params = {"force": "true"} if force else None
        data: dict[str, object] = await self._transport.request(
            HttpMethod.DELETE,
            f"/v1/datasets/{dataset_id}",
            params=params,
            response_model=dict,
        )
        return data
