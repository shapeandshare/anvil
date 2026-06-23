# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Corpus delete command — delete a corpus.

``CorpusDeleteCommand`` removes a corpus from the server via
``DELETE /v1/corpora/{id}``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class CorpusDeleteCommand(AbstractCommand):
    """Delete a corpus — ``DELETE /v1/corpora/{id}``."""

    async def execute(self, corpus_id: int) -> dict[str, object]:
        """Delete a corpus from the server.

        Parameters
        ----------
        corpus_id : int
            The corpus primary key.

        Returns
        -------
        dict[str, object]
            A response payload confirming the deletion.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.DELETE,
            f"/v1/corpora/{corpus_id}",
            response_model=dict,
        )
        return data
