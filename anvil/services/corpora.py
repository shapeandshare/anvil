from __future__ import annotations

import json

from anvil.db.models.corpus import Corpus, CorpusFile
from anvil.db.repositories.corpora import CorpusRepository
from anvil.services.corpus_loader import CorpusLoader


class CorpusService:
    def __init__(
        self, repo: CorpusRepository, loader: CorpusLoader | None = None
    ):
        self._repo = repo
        self._loader = loader or CorpusLoader()

    async def create(
        self,
        name: str,
        root_path: str,
        description: str | None = None,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        chunking_strategy: str = "windowed",
        chunk_overlap: float = 0.5,
        block_size: int = 16,
    ) -> Corpus:
        if chunking_strategy not in ("line", "windowed", "file"):
            raise ValueError(
                f"chunking_strategy must be one of: line, windowed, file"
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
        chunking_strategy: str | None = None,
        chunk_overlap: float | None = None,
        block_size: int | None = None,
    ) -> Corpus:
        """Create a new corpus variant (fork) from an existing one.

        Copies the source corpus's parameters (root_path, chunking config,
        include/exclude patterns) and applies any overrides. The new corpus
        has ``parent_id`` set to the source corpus for lineage tracking.

        Does NOT ingest automatically — call ``ingest()`` separately.
        """
        source = await self._repo.get(source_id)
        if source is None:
            raise ValueError(f"Corpus {source_id} not found")

        resolved_chunking = chunking_strategy or source.chunking_strategy
        if resolved_chunking not in ("line", "windowed", "file"):
            raise ValueError(
                f"chunking_strategy must be one of: line, windowed, file"
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
                json.loads(source.include_patterns)
                if source.include_patterns
                else None
            )
        )
        exc = (
            exclude_patterns
            if exclude_patterns is not None
            else (
                json.loads(source.exclude_patterns)
                if source.exclude_patterns
                else None
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
            block_size=(
                block_size if block_size is not None else source.block_size
            ),
            parent_id=source.id,
        )
        return await self._repo.add(corpus)

    async def list(self):
        return await self._repo.get_all()

    async def get(self, id: int) -> Corpus | None:
        return await self._repo.get(id)

    async def delete(self, id: int) -> bool:
        return await self._repo.delete(id)

    async def ingest(self, id: int, max_files: int = 10000) -> tuple[Corpus, list[str]]:
        corpus = await self._repo.get(id)
        if corpus is None:
            raise ValueError(f"Corpus {id} not found")

        inc = (
            json.loads(corpus.include_patterns)
            if corpus.include_patterns
            else None
        )
        exc = (
            json.loads(corpus.exclude_patterns)
            if corpus.exclude_patterns
            else None
        )

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

    async def load_docs(self, corpus_id: int) -> list[str]:
        corpus = await self._repo.get(corpus_id)
        if corpus is None:
            raise ValueError(f"Corpus {corpus_id} not found")
        inc = (
            json.loads(corpus.include_patterns)
            if corpus.include_patterns
            else None
        )
        exc = (
            json.loads(corpus.exclude_patterns)
            if corpus.exclude_patterns
            else None
        )
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
            chunker = self._loader._make_chunker(
                corpus.chunking_strategy, corpus.chunk_overlap, corpus.block_size
            )
            all_chunks.extend(chunker.chunk(text))
        return all_chunks

    async def get_files(self, corpus_id: int, language: str | None = None):
        return await self._repo.get_files(corpus_id, language)

    async def get_file(self, file_id: int):
        return await self._repo.get_file(file_id)