# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Corpus files command — list files in a corpus.

``CorpusFilesCommand`` lists the files belonging to a corpus via
``GET /v1/corpora/{id}/files[?language=]``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class CorpusFilesCommand(AbstractCommand):
    """List corpus files — ``GET /v1/corpora/{id}/files[?language=]``."""

    async def execute(
        self, corpus_id: int, language: str | None = None,
    ) -> list[dict[str, object]]:
        """List files belonging to a corpus.

        Parameters
        ----------
        corpus_id : int
            The corpus primary key.
        language : str | None, optional
            Optional language filter (e.g. ``"python"``, ``"markdown"``).

        Returns
        -------
        list[dict[str, object]]
            A list of file records as raw dictionaries.
        """
        params = {"language": language} if language else None
        data: list[dict[str, object]] = await self._transport.request(
            HttpMethod.GET,
            f"/v1/corpora/{corpus_id}/files",
            params=params,
            response_model=list,
        )
        return data
