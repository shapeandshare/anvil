# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Eval dataset create command — create an eval dataset.

``EvalDatasetCreateCommand`` creates a new evaluation dataset on the server
via ``POST /v1/eval-datasets``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class EvalDatasetCreateCommand(AbstractCommand):
    """Create an eval dataset — ``POST /v1/eval-datasets``."""

    async def execute(
        self,
        name: str,
        source: str,
        description: str | None = None,
    ) -> dict[str, object]:
        """Create a new evaluation dataset on the server.

        Parameters
        ----------
        name : str
            The dataset name.
        source : str
            The source path or corpus reference for the dataset.
        description : str | None, optional
            An optional description for the dataset.

        Returns
        -------
        dict[str, object]
            The newly created eval dataset record as a raw dictionary.
        """
        body: dict[str, object] = {"name": name, "source": source}
        if description is not None:
            body["description"] = description
        data: dict[str, object] = await self._transport.request(
            HttpMethod.POST,
            "/v1/eval-datasets",
            json=body,
            response_model=dict,
        )
        return data
