# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Registry register command — register a model from an experiment.

``RegistryRegisterCommand`` sends a ``POST /v1/registry/models`` request
with an ``experiment_id`` and returns the server's registration payload.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class RegistryRegisterCommand(AbstractCommand):
    """Register a model from an experiment — ``POST /v1/registry/models``."""

    async def execute(self, experiment_id: str) -> dict[str, object]:
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
        data: dict[str, object] = await self._transport.request(
            HttpMethod.POST,
            "/v1/registry/models",
            json={"experiment_id": experiment_id},
            response_model=dict,
        )
        return data
