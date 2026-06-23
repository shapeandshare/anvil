# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Registry delete command — delete a model or a specific model version.

``RegistryDeleteCommand`` sends a ``DELETE /v1/registry/models/{id}`` or
``DELETE /v1/registry/models/{id}/versions/{version}`` request and returns
the server's confirmation payload.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class RegistryDeleteCommand(AbstractCommand):
    """Delete a model or version — ``DELETE /v1/registry/models/{id}[/versions/{version}]``."""

    async def execute(
        self, model_id: str, version: str | None = None
    ) -> dict[str, object]:
        """Delete a registered model (all versions) or a specific version.

        Parameters
        ----------
        model_id : str
            The server-assigned model identifier to delete.
        version : str | None, optional
            If provided, only this specific version is deleted rather than
            the entire model. ``None`` deletes all versions of the model.

        Returns
        -------
        dict[str, object]
            A confirmation payload from the server.
        """
        path: str = f"/v1/registry/models/{model_id}"
        if version is not None:
            path = f"{path}/versions/{version}"
        data: dict[str, object] = await self._transport.request(
            HttpMethod.DELETE,
            path,
            response_model=dict,
        )
        return data
