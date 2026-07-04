# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SDK command for retrieving a single model from the unified catalog."""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ModelsGetCommand(AbstractCommand):
    """Retrieve a model via ``GET /v1/models/{name}`` from the unified catalog."""

    async def execute(self, name: str) -> dict[str, object]:
        """Return a single model by catalog name.

        Parameters
        ----------
        name : str
            Catalog model name.

        Returns
        -------
        dict
            Model metadata response including all versions.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.GET,
            f"/v1/models/{name}",
            response_model=dict,
        )
        return data
