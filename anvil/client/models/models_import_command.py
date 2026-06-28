# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SDK command for importing an external model."""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ModelsImportCommand(AbstractCommand):
    """Submit an external model import job via ``POST /v1/models/import``."""

    async def execute(
        self,
        source: str,
        identifier: str,
        *,
        revision: str = "main",
        name: str | None = None,
    ) -> dict[str, object]:
        """Submit an import and return the job ID and status.

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
        body: dict[str, object] = {
            "source": source,
            "identifier": identifier,
            "revision": revision,
        }
        if name is not None:
            body["name"] = name

        data: dict[str, object] = await self._transport.request(
            HttpMethod.POST,
            "/v1/models/import",
            json=body,
            response_model=dict,
        )
        return data
