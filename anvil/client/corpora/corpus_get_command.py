# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Corpus get command — fetch a single corpus.

``CorpusGetCommand`` retrieves a single corpus by its ID via
``GET /v1/corpora/{id}``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class CorpusGetCommand(AbstractCommand):
    """Get a single corpus — ``GET /v1/corpora/{id}``."""

    async def execute(self, corpus_id: int) -> dict[str, object]:
        """Fetch a single corpus by its primary key.

        Parameters
        ----------
        corpus_id : int
            The corpus primary key.

        Returns
        -------
        dict[str, object]
            The corpus record as a raw dictionary.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.GET,
            f"/v1/corpora/{corpus_id}",
            response_model=dict,
        )
        return data
