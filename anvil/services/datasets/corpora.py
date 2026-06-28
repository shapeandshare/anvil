# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Corpus management service — CRUD and ingestion orchestration for corpora.

Provides business logic for creating, forking, ingesting, listing, and
deleting corpora. Corpora represent collections of files from a directory
that are chunked into training documents.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from ...db.models.corpus import Corpus
from ...db.models.corpus_file import CorpusFile
from ...db.repositories.corpora import CorpusRepository
from ..chunking.base import Chunker as BaseChunker
from ..chunking.file_chunker import FileAsDocChunker
from ..chunking.line_chunker import LineAsDocChunker
from ..chunking.window_chunker import FixedSizeWindowChunker
from .chunking_strategy import ChunkingStrategy
from .corpus_loader import CorpusLoader


class CorpusService:
    """Business logic for corpus CRUD and file ingestion.

    Wraps a ``CorpusRepository`` and a ``CorpusLoader`` to provide
    higher-level operations such as creating a corpus with validation,
    forking an existing corpus, and ingesting files from a directory.
    """

    def __init__(self, repo: CorpusRepository, loader: CorpusLoader | None = None):
        """Initialise the service with a repository and optional loader.

        Parameters
        ----------
        repo : CorpusRepository
            Repository for corpus persistence.
        loader : CorpusLoader, optional
            Loader for directory walking and chunking. Defaults to a
            new ``CorpusLoader`` instance if not provided.
        """
        self._repo = repo
        self._loader = loader or CorpusLoader()

    async def create(
        self,
        name: str,
        root_path: str,
        description: str | None = None,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        chunking_strategy: ChunkingStrategy = ChunkingStrategy.WINDOWED,
        chunk_overlap: float = 0.5,
        block_size: int = 16,
    ) -> Corpus:
        """Create a new corpus with the given configuration.

        Validates ``chunking_strategy`` and ``chunk_overlap`` before
        persisting the corpus via the repository.

        Parameters
        ----------
        name : str
            Human-readable name for the corpus.
        root_path : str
            Absolute filesystem path to the directory to ingest.
        description : str, optional
            Optional description of the corpus. Defaults to ``None``.
        include_patterns : list[str], optional
            Glob patterns for files to include. Defaults to ``None``
            (uses loader defaults).
        exclude_patterns : list[str], optional
            Glob patterns for files to exclude. Defaults to ``None``.
        chunking_strategy : ChunkingStrategy
            Chunking strategy enum member. Defaults to
            ``ChunkingStrategy.WINDOWED``.
        chunk_overlap : float
            Overlap fraction for windowed chunking, in ``[0.0, 1.0]``.
            Defaults to ``0.5``.
        block_size : int
            Block size (token window) for chunking. Defaults to ``16``.

        Returns
        -------
        Corpus
            The newly created corpus record.

        Raises
        ------
        TypeError
            If ``chunking_strategy`` is not a ``ChunkingStrategy``
            instance.
        ValueError
            If ``chunk_overlap`` is outside ``[0.0, 1.0]``.
        """
        if isinstance(chunking_strategy, str):
            chunking_strategy = ChunkingStrategy(chunking_strategy)
        elif not isinstance(chunking_strategy, ChunkingStrategy):
            raise TypeError(
                "chunking_strategy must be a ChunkingStrategy enum member or string"
            )
        if not 0.0 <= chunk_overlap <= 1.0:
            raise ValueError(
                f"chunk_overlap must be in [0.0, 1.0], got {chunk_overlap}"
            )
        corpus = Corpus(
            name=name,
            description=description,
            root_path=root_path,
            include_patterns=(
                json.dumps(include_patterns) if include_patterns else None
            ),
            exclude_patterns=(
                json.dumps(exclude_patterns) if exclude_patterns else None
            ),
            chunking_strategy=chunking_strategy,
            chunk_overlap=chunk_overlap,
            block_size=block_size,
        )
        return await self._repo.add(corpus)

    async def fork(
        self,
        source_id: int,
        name: str,
        description: str | None = None,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        chunking_strategy: ChunkingStrategy | None = None,
        chunk_overlap: float | None = None,
        block_size: int | None = None,
    ) -> Corpus:
        """Create a new corpus variant (fork) from an existing one.

        Copies the source corpus's parameters (root_path, chunking config,
        include/exclude patterns) and applies any overrides. The new corpus
        has ``parent_id`` set to the source corpus for lineage tracking.

        Does NOT ingest automatically — call ``ingest()`` separately.

        Parameters
        ----------
        source_id : int
            ID of the source corpus to fork from.
        name : str
            Name for the new corpus.
        description : str, optional
            Optional description override.
        include_patterns : list[str], optional
            Override include patterns.
        exclude_patterns : list[str], optional
            Override exclude patterns.
        chunking_strategy : ChunkingStrategy, optional
            Override chunking strategy. Defaults to source corpus
            value.
        chunk_overlap : float, optional
            Override chunk overlap. Defaults to source corpus value.
        block_size : int, optional
            Override block size. Defaults to source corpus value.

        Returns
        -------
        Corpus
            The newly created fork.

        Raises
        ------
        ValueError
            If ``source_id`` is not found, or if ``chunk_overlap``
            is outside ``[0.0, 1.0]``.
        TypeError
            If ``chunking_strategy`` is not a ``ChunkingStrategy``
            instance when provided.
        """
        source = await self._repo.get(source_id)
        if source is None:
            raise ValueError(f"Corpus {source_id} not found")

        resolved_chunking = chunking_strategy or source.chunking_strategy
        if isinstance(resolved_chunking, str):
            resolved_chunking = ChunkingStrategy(resolved_chunking)
        elif not isinstance(resolved_chunking, ChunkingStrategy):
            raise TypeError(
                "chunking_strategy must be a ChunkingStrategy enum member or string"
            )
        resolved_overlap = (
            chunk_overlap if chunk_overlap is not None else source.chunk_overlap
        )
        if not 0.0 <= resolved_overlap <= 1.0:
            raise ValueError(
                f"chunk_overlap must be in [0.0, 1.0], got {resolved_overlap}"
            )

        inc = (
            include_patterns
            if include_patterns is not None
            else (
                json.loads(source.include_patterns) if source.include_patterns else None
            )
        )
        exc = (
            exclude_patterns
            if exclude_patterns is not None
            else (
                json.loads(source.exclude_patterns) if source.exclude_patterns else None
            )
        )

        corpus = Corpus(
            name=name,
            description=description if description is not None else source.description,
            root_path=source.root_path,
            include_patterns=json.dumps(inc) if inc else None,
            exclude_patterns=json.dumps(exc) if exc else None,
            chunking_strategy=resolved_chunking,
            chunk_overlap=resolved_overlap,
            block_size=(block_size if block_size is not None else source.block_size),
            parent_id=source.id,
        )
        return await self._repo.add(corpus)

    async def list_all(self) -> Sequence[Corpus]:
        """Return all corpora.

        Returns
        -------
        Sequence[Corpus]
            All corpus records from the repository.
        """
        return await self._repo.get_all()

    async def get(self, corpus_id: int) -> Corpus | None:
        """Retrieve a single corpus by its ID.

        Parameters
        ----------
        corpus_id : int
            The corpus ID.

        Returns
        -------
        Corpus or None
            The corpus record if found, ``None`` otherwise.
        """
        return await self._repo.get(corpus_id)

    async def delete(self, corpus_id: int) -> bool:
        """Delete a corpus by its ID.

        Parameters
        ----------
        corpus_id : int
            The corpus ID to delete.

        Returns
        -------
        bool
            ``True`` if the corpus was deleted, ``False`` if not found.
        """
        return await self._repo.delete(corpus_id)

    async def ingest(
        self, corpus_id: int, max_files: int = 10000
    ) -> tuple[Corpus, list[str]]:
        """Ingest files from the corpus directory into the database.

        Walks the corpus root directory, chunks files according to the
        corpus configuration, and stores file metadata as ``CorpusFile``
        records. Replaces any previously ingested files.

        Parameters
        ----------
        corpus_id : int
            The corpus ID to ingest.
        max_files : int
            Maximum number of files to ingest. Defaults to ``10000``.

        Returns
        -------
        tuple[Corpus, list[str]]
            The updated corpus record and a list of error messages.

        Raises
        ------
        ValueError
            If no corpus with the given ``corpus_id`` exists.
        """
        corpus = await self._repo.get(corpus_id)
        if corpus is None:
            raise ValueError(f"Corpus {corpus_id} not found")

        inc = json.loads(corpus.include_patterns) if corpus.include_patterns else None
        exc = json.loads(corpus.exclude_patterns) if corpus.exclude_patterns else None

        result = self._loader.ingest(
            root_path=corpus.root_path,
            include_patterns=inc,
            exclude_patterns=exc,
            chunking_strategy=corpus.chunking_strategy,
            chunk_overlap=corpus.chunk_overlap,
            block_size=corpus.block_size,
            max_files=max_files,
        )

        await self._repo.delete_files_for_corpus(corpus.id)

        for fd in result.files:
            cf = CorpusFile(
                corpus_id=corpus.id,
                relative_path=fd["relative_path"],
                language=fd["language"],
                line_count=fd["line_count"],
                char_count=fd["char_count"],
                chunk_count=fd["chunk_count"],
                encoding=fd["encoding"],
                size_bytes=fd["size_bytes"],
            )
            await self._repo.add_file(cf)

        corpus.file_count = len(result.files)
        corpus.document_count = result.total_docs
        corpus.language_map = json.dumps(result.language_map)
        corpus.errors = json.dumps(result.errors) if result.errors else None
        return corpus, result.errors

    async def scan_and_chunk(
        self,
        corpus_id: int,
        chunking_strategy: str = "windowed",
        chunk_overlap: float = 0.5,
        block_size: int | None = None,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> list[str]:
        """Scan a corpus directory and chunk files with custom parameters.

        Loads the file listing using the corpus's include/exclude patterns
        (optionally overridden), reads each file's text content, and
        chunks using the requested strategy.  This is independent of the
        corpus's stored chunking configuration.

        Parameters
        ----------
        corpus_id : int
            The corpus ID to scan.
        chunking_strategy : str
            One of ``"line"``, ``"file"``, or ``"windowed"``.
        chunk_overlap : float
            Overlap fraction for windowed chunking. Defaults to ``0.5``.
        block_size : int, optional
            Block size for windowed chunking. ``None`` defaults to
            the corpus's stored ``block_size``.
        include_patterns : list[str], optional
            Override include glob patterns. ``None`` uses corpus default.
        exclude_patterns : list[str], optional
            Override exclude glob patterns. ``None`` uses corpus default.

        Returns
        -------
        list[str]
            Chunked document strings.

        Raises
        ------
        ValueError
            If the corpus is not found.
        """
        corpus = await self._repo.get(corpus_id)
        if corpus is None:
            raise ValueError(f"Corpus {corpus_id} not found")

        inc = (
            include_patterns
            if include_patterns is not None
            else (
                json.loads(corpus.include_patterns) if corpus.include_patterns else None
            )
        )
        exc = (
            exclude_patterns
            if exclude_patterns is not None
            else (
                json.loads(corpus.exclude_patterns) if corpus.exclude_patterns else None
            )
        )

        load_result = self._loader.ingest(
            root_path=corpus.root_path,
            include_patterns=inc,
            exclude_patterns=exc,
            chunking_strategy=chunking_strategy,
            chunk_overlap=chunk_overlap,
            block_size=block_size or corpus.block_size,
        )

        if chunking_strategy == "line":
            chunker: BaseChunker = LineAsDocChunker()
        elif chunking_strategy == "file":
            chunker = FileAsDocChunker()
        else:
            bs = block_size or corpus.block_size or 16
            chunker = FixedSizeWindowChunker(block_size=bs, overlap=chunk_overlap)

        docs: list[str] = []
        for fd in load_result.files:
            full_path = Path(corpus.root_path) / fd["relative_path"]
            try:
                text = full_path.read_text("utf-8")
            except (FileNotFoundError, UnicodeDecodeError):
                continue
            docs.extend(chunker.chunk(text))
        return docs

    async def load_docs(self, corpus_id: int) -> list[str]:
        """Load and chunk all documents for a corpus.

        Re-ingests the corpus directory and returns the chunked text
        content as a flat list of document strings.

        Parameters
        ----------
        corpus_id : int
            The corpus ID to load documents for.

        Returns
        -------
        list[str]
            All chunked documents as strings.

        Raises
        ------
        ValueError
            If no corpus with the given ``corpus_id`` exists.
        """
        corpus = await self._repo.get(corpus_id)
        if corpus is None:
            raise ValueError(f"Corpus {corpus_id} not found")
        inc = json.loads(corpus.include_patterns) if corpus.include_patterns else None
        exc = json.loads(corpus.exclude_patterns) if corpus.exclude_patterns else None
        result = self._loader.ingest(
            root_path=corpus.root_path,
            include_patterns=inc,
            exclude_patterns=exc,
            chunking_strategy=corpus.chunking_strategy,
            chunk_overlap=corpus.chunk_overlap,
            block_size=corpus.block_size,
        )
        all_chunks: list[str] = []
        for fd in result.files:
            text = (
                __import__("pathlib")
                .Path(corpus.root_path, fd["relative_path"])
                .read_text("utf-8")
            )
            chunker = self._loader._make_chunker(  # pylint: disable=protected-access
                corpus.chunking_strategy, corpus.chunk_overlap, corpus.block_size
            )
            all_chunks.extend(chunker.chunk(text))
        return all_chunks

    async def get_files(
        self, corpus_id: int, language: str | None = None
    ) -> Sequence[CorpusFile]:
        """Return the ingested files for a corpus, optionally filtered by language.

        Parameters
        ----------
        corpus_id : int
            The corpus ID.
        language : str, optional
            If provided, only return files with this language label.
            Defaults to ``None`` (return all files).

        Returns
        -------
        Sequence[CorpusFile]
            The matching file records.
        """
        return await self._repo.get_files(corpus_id, language)

    async def get_file(self, file_id: int) -> CorpusFile | None:
        """Return a single ingested file by its ID.

        Parameters
        ----------
        file_id : int
            The file ID.

        Returns
        -------
        CorpusFile or None
            The file record if found, ``None`` otherwise.
        """
        return await self._repo.get_file(file_id)
