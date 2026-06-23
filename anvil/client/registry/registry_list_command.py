# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Registry list command — list registered models.

``RegistryListCommand`` sends a ``GET /v1/registry/models`` request with an
optional ``search`` query parameter and returns a list of registered model
summaries.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class RegistryListCommand(AbstractCommand):
    """List registered models — ``GET /v1/registry/models[?search=]``."""

    async def execute(self, search: str | None = None) -> list[dict[str, object]]:
        """Fetch a list of registered models, optionally filtered by search.

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
        params: dict[str, str] | None = None
        if search is not None:
            params = {"search": search}
        data: dict[str, object] = await self._transport.request(
            HttpMethod.GET,
            "/v1/registry/models",
            params=params,
            response_model=dict,
        )
        # The envelope wraps the list under a key; narrow with isinstance.
        result: list[dict[str, object]] = []
        raw_models = data.get("models", [])
        if isinstance(raw_models, list):
            for item in raw_models:
                if isinstance(item, dict):
                    result.append(item)
        return result
