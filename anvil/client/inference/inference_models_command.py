# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Inference models command — list available models.

``InferenceModelsCommand`` retrieves the set of models available for inference
by issuing ``GET /v1/inference/models``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class InferenceModelsCommand(AbstractCommand):
    """List available inference models — ``GET /v1/inference/models``.

    Returns a dict with model metadata (IDs, names, statuses).
    """

    async def execute(self) -> dict[str, object]:
        """Retrieve the list of available inference models.

        Returns
        -------
        dict[str, object]
            Model listing from the server.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.GET,
            "/v1/inference/models",
            response_model=dict,
        )
        return data
