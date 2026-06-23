# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Inference sample command — generate text from a model.

``InferenceSampleCommand`` sends a prompt to a specific model and returns
generated text by issuing ``POST /v1/inference/sample``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class InferenceSampleCommand(AbstractCommand):
    """Generate sample text from a model — ``POST /v1/inference/sample``.

    Sends a prompt to the specified model and returns the generated
    continuation along with metadata.
    """

    async def execute(
        self,
        model_id: str,
        prompt: str,
        temperature: float = 0.7,
    ) -> dict[str, object]:
        """Send a prompt to a model and retrieve generated text.

        Parameters
        ----------
        model_id : str
            Identifier of the model to sample from.
        prompt : str
            Input text to condition the generation on.
        temperature : float, optional
            Sampling temperature. Higher values produce more random
            output. Defaults to ``0.7``.

        Returns
        -------
        dict[str, object]
            Generated text and sampling metadata.
        """
        body = {
            "model_id": model_id,
            "prompt": prompt,
            "temperature": temperature,
        }
        data: dict[str, object] = await self._transport.request(
            HttpMethod.POST,
            "/v1/inference/sample",
            json=body,
            response_model=dict,
        )
        return data
