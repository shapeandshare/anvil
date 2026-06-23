# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Corpora client — domain aggregator for corpus management operations.

``CorporaClient`` provides a single entry point for all corpus operations:
create, list, get, delete, files, ingest, and analyze-path. It delegates each
operation to its corresponding command class.
"""

from __future__ import annotations

import builtins

from .._shared.transport import Transport
from .corpus_analyze_path_command import CorpusAnalyzePathCommand
from .corpus_create_command import CorpusCreateCommand
from .corpus_delete_command import CorpusDeleteCommand
from .corpus_files_command import CorpusFilesCommand
from .corpus_get_command import CorpusGetCommand
from .corpus_ingest_command import CorpusIngestCommand
from .corpus_list_command import CorpusListCommand


class CorporaClient:
    """Corpus lifecycle operations.

    Aggregates all corpus commands behind a single facade. Each public
    method maps to one server API operation.

    Parameters
    ----------
    transport : Transport
        The shared SDK transport instance.
    """

    def __init__(self, transport: Transport) -> None:
        self._create_cmd = CorpusCreateCommand(transport)
        self._list_cmd = CorpusListCommand(transport)
        self._get_cmd = CorpusGetCommand(transport)
        self._delete_cmd = CorpusDeleteCommand(transport)
        self._files_cmd = CorpusFilesCommand(transport)
        self._ingest_cmd = CorpusIngestCommand(transport)
        self._analyze_path_cmd = CorpusAnalyzePathCommand(transport)

    async def create(
        self,
        name: str,
        description: str | None = None,
    ) -> dict[str, object]:
        """Create a new corpus.

        Parameters
        ----------
        name : str
            The corpus name.
        description : str | None, optional
            An optional description.

        Returns
        -------
        dict[str, object]
            The newly created corpus record.
        """
        return await self._create_cmd.execute(name, description=description)

    async def list(self) -> builtins.list[dict[str, object]]:
        """List all corpora.

        Returns
        -------
        List[dict[str, object]]
            A list of corpus records.
        """
        return await self._list_cmd.execute()

    async def get(self, corpus_id: int) -> dict[str, object]:
        """Get a single corpus by its primary key.

        Parameters
        ----------
        corpus_id : int
            The corpus primary key.

        Returns
        -------
        dict[str, object]
            The corpus record.
        """
        return await self._get_cmd.execute(corpus_id)

    async def delete(self, corpus_id: int) -> dict[str, object]:
        """Delete a corpus.

        Parameters
        ----------
        corpus_id : int
            The corpus primary key.

        Returns
        -------
        dict[str, object]
            A response payload confirming the deletion.
        """
        return await self._delete_cmd.execute(corpus_id)

    async def files(
        self,
        corpus_id: int,
        language: str | None = None,
    ) -> builtins.list[dict[str, object]]:
        """List files belonging to a corpus.

        Parameters
        ----------
        corpus_id : int
            The corpus primary key.
        language : str | None, optional
            Optional language filter.

        Returns
        -------
        List[dict[str, object]]
            A list of file records.
        """
        return await self._files_cmd.execute(corpus_id, language=language)

    async def ingest(
        self,
        corpus_id: int,
        max_files: int | None = None,
    ) -> dict[str, object]:
        """Trigger ingestion of files into a corpus.

        Parameters
        ----------
        corpus_id : int
            The corpus primary key.
        max_files : int | None, optional
            Maximum number of files to ingest.

        Returns
        -------
        dict[str, object]
            The server response with ingestion status.
        """
        return await self._ingest_cmd.execute(corpus_id, max_files=max_files)

    async def analyze_path(self, path: str) -> dict[str, object]:
        """Analyze a filesystem path for discoverable corpus files.

        Parameters
        ----------
        path : str
            The filesystem path to analyze.

        Returns
        -------
        dict[str, object]
            Metadata about files discoverable at the given path.
        """
        return await self._analyze_path_cmd.execute(path)
