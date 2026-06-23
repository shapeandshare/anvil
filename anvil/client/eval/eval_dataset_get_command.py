# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Eval dataset get command — fetch a single eval dataset.

``EvalDatasetGetCommand`` retrieves a single evaluation dataset by its name
via ``GET /v1/eval-datasets/{name}``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class EvalDatasetGetCommand(AbstractCommand):
    """Get a single eval dataset — ``GET /v1/eval-datasets/{name}``."""

    async def execute(self, name: str) -> dict[str, object]:
        """Fetch a single evaluation dataset by name.

        Parameters
        ----------
        name : str
            The evaluation dataset name.

        Returns
        -------
        dict[str, object]
            The eval dataset record as a raw dictionary.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.GET,
            f"/v1/eval-datasets/{name}",
            response_model=dict,
        )
        return data
