# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Corpus ingest command — ingest files into a corpus.

``CorpusIngestCommand`` triggers ingestion of files into a corpus via
``POST /v1/corpora/{id}/ingest[?max_files=]``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class CorpusIngestCommand(AbstractCommand):
    """Ingest files into a corpus — ``POST /v1/corpora/{id}/ingest[?max_files=]``."""

    async def execute(
        self, corpus_id: int, max_files: int | None = None,
    ) -> dict[str, object]:
        """Trigger ingestion of files into a corpus.

        Parameters
        ----------
        corpus_id : int
            The corpus primary key.
        max_files : int | None, optional
            Maximum number of files to ingest. ``None`` means no limit.

        Returns
        -------
        dict[str, object]
            The server response with ingestion status.
        """
        params = {"max_files": str(max_files)} if max_files else None
        data: dict[str, object] = await self._transport.request(
            HttpMethod.POST,
            f"/v1/corpora/{corpus_id}/ingest",
            params=params,
            response_model=dict,
        )
        return data
