# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Eval perplexity command — compute perplexity score.

``EvalPerplexityCommand`` triggers a perplexity evaluation on a trained model
via ``POST /v1/eval/perplexity``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class EvalPerplexityCommand(AbstractCommand):
    """Compute perplexity — ``POST /v1/eval/perplexity``."""

    async def execute(
        self,
        model_id: str,
        dataset_name: str,
        max_samples: int | None = None,
    ) -> dict[str, object]:
        """Compute perplexity for a trained model.

        Parameters
        ----------
        model_id : str
            The identifier of the model to evaluate.
        dataset_name : str
            The name of the eval dataset to use.
        max_samples : int | None, optional
            Maximum number of samples to evaluate. ``None`` means no limit.

        Returns
        -------
        dict[str, object]
            The evaluation result including perplexity score.
        """
        body: dict[str, object] = {
            "model_id": model_id,
            "dataset_name": dataset_name,
        }
        if max_samples is not None:
            body["max_samples"] = max_samples
        data: dict[str, object] = await self._transport.request(
            HttpMethod.POST,
            "/v1/eval/perplexity",
            json=body,
            response_model=dict,
        )
        return data
