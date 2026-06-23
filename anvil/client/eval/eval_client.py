# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Eval client — domain aggregator for evaluation operations.

``EvalClient`` provides a single entry point for all evaluation operations:
perplexity scoring and eval dataset management. It delegates each operation
to its corresponding command class.
"""

from __future__ import annotations

from .._shared.transport import Transport
from .eval_dataset_create_command import EvalDatasetCreateCommand
from .eval_dataset_get_command import EvalDatasetGetCommand
from .eval_perplexity_command import EvalPerplexityCommand


class EvalClient:
    """Model evaluation operations.

    Aggregates all eval commands behind a single facade. Each public method
    maps to one server API operation.

    Parameters
    ----------
    transport : Transport
        The shared SDK transport instance.
    """

    def __init__(self, transport: Transport) -> None:
        self._perplexity_cmd = EvalPerplexityCommand(transport)
        self._dataset_create_cmd = EvalDatasetCreateCommand(transport)
        self._dataset_get_cmd = EvalDatasetGetCommand(transport)

    async def perplexity(
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
            Maximum number of samples to evaluate.

        Returns
        -------
        dict[str, object]
            The evaluation result including perplexity score.
        """
        return await self._perplexity_cmd.execute(
            model_id,
            dataset_name,
            max_samples=max_samples,
        )

    async def create_dataset(
        self,
        name: str,
        source: str,
        description: str | None = None,
    ) -> dict[str, object]:
        """Create a new evaluation dataset.

        Parameters
        ----------
        name : str
            The dataset name.
        source : str
            The source path or corpus reference.
        description : str | None, optional
            An optional description.

        Returns
        -------
        dict[str, object]
            The newly created eval dataset record.
        """
        return await self._dataset_create_cmd.execute(
            name,
            source,
            description=description,
        )

    async def get_dataset(self, name: str) -> dict[str, object]:
        """Get an evaluation dataset by name.

        Parameters
        ----------
        name : str
            The evaluation dataset name.

        Returns
        -------
        dict[str, object]
            The eval dataset record.
        """
        return await self._dataset_get_cmd.execute(name)
