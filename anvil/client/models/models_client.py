# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SDK domain aggregator for the external model API."""

from __future__ import annotations

from .._shared.transport import Transport
from .models_get_command import ModelsGetCommand
from .models_get_status_command import ModelsGetStatusCommand
from .models_import_command import ModelsImportCommand


class ModelsClient:
    """Domain client for the external model import and registry API.

    Parameters
    ----------
    transport : Transport
        Shared HTTP transport bound to a server configuration.
    """

    def __init__(self, transport: Transport) -> None:
        self._import_cmd = ModelsImportCommand(transport)
        self._status_cmd = ModelsGetStatusCommand(transport)
        self._get_cmd = ModelsGetCommand(transport)

    async def import_model(
        self,
        source: str,
        identifier: str,
        *,
        revision: str = "main",
        name: str | None = None,
    ) -> dict[str, object]:
        """Submit an external model import job.

        Parameters
        ----------
        source : str
            Source type (``"huggingface"`` or ``"local"``).
        identifier : str
            Source-specific model identifier.
        revision : str
            Source revision. Defaults to ``"main"``.
        name : str | None
            Optional display name.

        Returns
        -------
        dict
            Response with ``job_id`` and ``status`` keys.
        """
        return await self._import_cmd.execute(
            source=source,
            identifier=identifier,
            revision=revision,
            name=name,
        )

    async def get_import_status(self, job_id: int) -> dict[str, object]:
        """Poll the status of an import job.

        Parameters
        ----------
        job_id : int
            Import job ID from ``import_model()``.

        Returns
        -------
        dict
            Job status response with ``status``, ``error_code``,
            and ``external_model_id``.
        """
        return await self._status_cmd.execute(job_id)

    async def get(self, model_id: int) -> dict[str, object]:
        """Retrieve a single external model by ID.

        Parameters
        ----------
        model_id : int
            External model primary key.

        Returns
        -------
        dict
            Model metadata response.
        """
        return await self._get_cmd.execute(model_id)
