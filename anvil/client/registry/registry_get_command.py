# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Registry get command — fetch a single registered model by ID.

``RegistryGetCommand`` sends a ``GET /v1/registry/models/{id}`` request
and returns the server's model detail payload.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class RegistryGetCommand(AbstractCommand):
    """Fetch a registered model — ``GET /v1/registry/models/{id}``."""

    async def execute(self, model_id: str) -> dict[str, object]:
        """Fetch details for a single registered model.

        Parameters
        ----------
        model_id : str
            The server-assigned model identifier.

        Returns
        -------
        dict[str, object]
            The model detail payload including metadata and version list.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.GET,
            f"/v1/registry/models/{model_id}",
            response_model=dict,
        )
        return data
