# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Registry client — domain aggregator for model registry operations.

``RegistryClient`` provides a single entry point for all model registry
operations: register, list, get, and delete. It delegates each operation
to its corresponding command class.
"""

from __future__ import annotations

from .._shared.transport import Transport
from .registry_delete_command import RegistryDeleteCommand
from .registry_get_command import RegistryGetCommand
from .registry_list_command import RegistryListCommand
from .registry_register_command import RegistryRegisterCommand


class RegistryClient:
    """Model registry lifecycle operations.

    Aggregates all registry commands behind a single facade. Each public
    method maps to one server API operation.

    Parameters
    ----------
    transport : Transport
        The shared SDK transport instance.
    """

    def __init__(self, transport: Transport) -> None:
        self._register_cmd = RegistryRegisterCommand(transport)
        self._list_cmd = RegistryListCommand(transport)
        self._get_cmd = RegistryGetCommand(transport)
        self._delete_cmd = RegistryDeleteCommand(transport)

    async def register(self, experiment_id: str) -> dict[str, object]:
        """Register a new model from the given experiment.

        Parameters
        ----------
        experiment_id : str
            The MLflow experiment identifier whose best model should be
            registered.

        Returns
        -------
        dict[str, object]
            The server response payload containing the newly registered
            model metadata.
        """
        return await self._register_cmd.execute(experiment_id)

    async def list(self, search: str | None = None) -> list[dict[str, object]]:
        """List registered models, optionally filtered by search term.

        Parameters
        ----------
        search : str | None, optional
            Optional search term to filter models by name or identifier.
            ``None`` returns all registered models.

        Returns
        -------
        list[dict[str, object]]
            A list of registered model summary payloads.
        """
        return await self._list_cmd.execute(search)

    async def get(self, model_id: str) -> dict[str, object]:
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
        return await self._get_cmd.execute(model_id)

    async def delete(self, model_id: str, version: str | None = None) -> dict[str, object]:
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
        return await self._delete_cmd.execute(model_id, version)
