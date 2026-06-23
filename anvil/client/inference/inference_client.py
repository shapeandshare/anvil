# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Inference client — domain aggregator for model inference operations.

``InferenceClient`` provides ``models()`` for listing available models and
``sample()`` for generating text, delegating to
``InferenceModelsCommand`` and ``InferenceSampleCommand`` respectively.
"""

from __future__ import annotations

from .._shared.transport import Transport
from .inference_models_command import InferenceModelsCommand
from .inference_sample_command import InferenceSampleCommand


class InferenceClient:
    """Model inference operations.

    Provides ``models()`` for listing available models and ``sample()`` for
    generating text from a model.

    Parameters
    ----------
    transport : Transport
        The shared SDK transport instance.
    """

    def __init__(self, transport: Transport) -> None:
        self._models = InferenceModelsCommand(transport)
        self._sample = InferenceSampleCommand(transport)

    async def models(self) -> dict[str, object]:
        """List available inference models.

        Returns
        -------
        dict[str, object]
            Model listing from the server.
        """
        return await self._models.execute()

    async def sample(
        self,
        model_id: str,
        prompt: str,
        temperature: float = 0.7,
    ) -> dict[str, object]:
        """Generate text from a model.

        Parameters
        ----------
        model_id : str
            Identifier of the model to sample from.
        prompt : str
            Input text to condition the generation on.
        temperature : float, optional
            Sampling temperature. Defaults to ``0.7``.

        Returns
        -------
        dict[str, object]
            Generated text and sampling metadata.
        """
        return await self._sample.execute(model_id, prompt, temperature)