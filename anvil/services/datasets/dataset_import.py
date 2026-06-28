# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Dataset import service — parses and imports text into datasets.

Provides the ``DatasetImportService`` class for parsing text in various
formats (TXT, CSV, JSONL, JSON, paste, corpus) and committing the
parsed samples to a dataset with file storage.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models.curation_operation import CurationOperation
from ...db.models.import_source import ImportSource
from ...db.models.sample import Sample
from ...db.repositories.curation import SampleRepository
from ...db.repositories.curation_operation_repository import CurationOperationRepository
from ...db.repositories.datasets import DatasetRepository
from ...db.repositories.import_source_repository import ImportSourceRepository
from ...storage.local import LocalFileStore
from .dataset_status import DatasetStatus
from .import_result import ImportResult
from .parsed_sample import ParsedSample

if TYPE_CHECKING:
    from ...workspace.workspace_paths import WorkspacePaths


class DatasetImportService:
    """Parses text in various formats and imports samples into a dataset.

    Supports TXT (one sample per line), CSV, JSONL, JSON, paste
    (same as TXT), and corpus formats. Commits parsed samples to the
    database and stores their content in the file store.
    """

    def __init__(
        self,
        session: AsyncSession,
        dataset_id: int,
        store: LocalFileStore | None = None,
        paths: WorkspacePaths | None = None,
    ):
        """Initialise the import service.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session for database access.
        dataset_id : int
            ID of the dataset to import into.
        store : LocalFileStore, optional
            File store for persisting sample content.  When ``None``
            and *paths* is provided the store is rooted at
            ``paths.datasets_dir``, otherwise it falls back to
            ``"data/datasets"``.
        paths : WorkspacePaths, optional
            When provided with no explicit *store*, the store is created
            from ``paths.datasets_dir``.
        """
        self._session = session
        self._dataset_id = dataset_id
        if store is not None:
            self._store = store
        elif paths is not None:
            self._store = LocalFileStore(str(paths.datasets_dir))
        else:
            self._store = LocalFileStore("data/datasets")
        self._sample_repo = SampleRepository(session)
        self._op_repo = CurationOperationRepository(session)
        self._import_repo = ImportSourceRepository(session)
        self._dataset_repo = DatasetRepository(session)

    async def preview_import(
        self, text: str | None = None, fmt: str = "txt", max_rows: int = 20
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Parse text and return a preview without committing.

        Useful for showing the user what will be imported before the
        actual commit.

        Parameters
        ----------
        text : str, optional
            The raw text to parse. ``None`` or empty string returns
            empty preview and errors.
        fmt : str
            Input format: ``"txt"``, ``"csv"``, ``"jsonl"``,
            ``"json"``, ``"paste"``, or ``"corpus"``. Defaults to
            ``"txt"``.
        max_rows : int
            Maximum preview rows to return. Defaults to ``20``.

        Returns
        -------
        tuple[list[dict], list[dict]]
            Preview dicts (with keys ``"index"``, ``"text_preview"``,
            ``"length"``) and error dicts.
        """
        samples, errors = self._parse(text or "", fmt)
        preview = [
            {"index": s.index, "text_preview": s.text[:200], "length": s.length}
            for s in samples[:max_rows]
        ]
        return preview, errors

    async def commit_import(self, text: str, fmt: str = "txt") -> ImportResult:
        """Parse and commit text samples into the dataset.

        Parses the input text, creates sample records in the database,
        writes sample content to the file store, and updates dataset
        metadata. Runs within a transaction that is rolled back on
        failure.

        Parameters
        ----------
        text : str
            The raw text to parse and import.
        fmt : str
            Input format. Defaults to ``"txt"``.

        Returns
        -------
        ImportResult
            Outcome including import source ID, rows imported, errors,
            and preview.

        Raises
        ------
        ValueError
            If the dataset is not found.
        """
        samples, errors = self._parse(text, fmt)
        if not samples:
            return ImportResult(
                import_source_id=0,
                rows_imported=0,
                errors=errors,
                preview=[],
            )

        dataset = await self._dataset_repo.get(self._dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {self._dataset_id} not found")

        dataset.status = DatasetStatus.IMPORTING
        await self._dataset_repo.update(dataset)

        try:
            import_source = ImportSource(
                dataset_id=self._dataset_id,
                filename="import",
                format=fmt,
                row_count=len(samples),
                error_count=len(errors),
            )
            import_source = await self._import_repo.add(import_source)

            sample_records = []
            for s in samples:
                file_rel = f"{self._dataset_id}/{import_source.id}/{s.index}.txt"
                sample_records.append(
                    Sample(
                        dataset_id=self._dataset_id,
                        index=s.index,
                        content_hash=s.content_hash,
                        length=s.length,
                        file_path=file_rel,
                        is_removed=False,
                        import_source_id=import_source.id,
                    )
                )

            sample_records = await self._sample_repo.add_bulk(sample_records)

            for s, _rec in zip(samples, sample_records, strict=True):
                rel_path = f"{self._dataset_id}/{import_source.id}/{s.index}.txt"
                await self._store.put(
                    rel_path,
                    self._text_stream(s.text),
                )

            before_count = await self._sample_repo.count_active(self._dataset_id)
            after_count = before_count + len(sample_records)

            op = CurationOperation(
                dataset_id=self._dataset_id,
                operation_type="import",
                parameters=f'{{"format": "{fmt}", "filename": "import", "row_count": {len(samples)}}}',
                sample_count_before=before_count,
                sample_count_after=after_count,
            )
            await self._op_repo.add(op)

            dataset.sample_count = after_count
            dataset.total_size_bytes = (dataset.total_size_bytes or 0) + sum(
                s.length for s in samples
            )
            dataset.curation_version = (dataset.curation_version or 0) + 1
            dataset.status = (
                DatasetStatus.READY if after_count > 0 else DatasetStatus.EMPTY
            )
            await self._dataset_repo.update(dataset)

            preview = [
                {"index": s.index, "text_preview": s.text[:200], "length": s.length}
                for s in samples[:20]
            ]

            await self._session.commit()

            return ImportResult(
                import_source_id=import_source.id,
                rows_imported=len(sample_records),
                errors=errors,
                preview=preview,
            )
        except Exception:
            await self._session.rollback()
            dataset.status = (
                DatasetStatus.READY if dataset.sample_count > 0 else DatasetStatus.EMPTY
            )
            await self._dataset_repo.update(dataset)
            raise

    async def commit_docs_import(
        self,
        docs: list[str],
        source_label: str = "import",
        source_format: str = "docs",
    ) -> ImportResult:
        """Import a list of pre-parsed document strings.

        Creates sample records, writes content to the file store,
        and updates dataset metadata in a transaction.

        Parameters
        ----------
        docs : list[str]
            Pre-parsed document strings to import.
        source_label : str
            Label for the import source. Defaults to ``"import"``.
        source_format : str
            Format identifier for the import source. Defaults to
            ``"docs"``.

        Returns
        -------
        ImportResult
            Outcome including import source ID, rows imported, errors,
            and preview.

        Raises
        ------
        ValueError
            If the dataset is not found.
        """
        if not docs:
            return ImportResult(
                import_source_id=0,
                rows_imported=0,
                errors=[],
                preview=[],
            )

        dataset = await self._dataset_repo.get(self._dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {self._dataset_id} not found")

        dataset.status = DatasetStatus.IMPORTING
        await self._dataset_repo.update(dataset)

        samples = [ParsedSample(text, idx) for idx, text in enumerate(docs)]

        try:
            import_source = ImportSource(
                dataset_id=self._dataset_id,
                filename=source_label,
                format=source_format,
                row_count=len(samples),
                error_count=0,
            )
            import_source = await self._import_repo.add(import_source)

            sample_records = []
            for s in samples:
                file_rel = f"{self._dataset_id}/{import_source.id}/{s.index}.txt"
                sample_records.append(
                    Sample(
                        dataset_id=self._dataset_id,
                        index=s.index,
                        content_hash=s.content_hash,
                        length=s.length,
                        file_path=file_rel,
                        is_removed=False,
                        import_source_id=import_source.id,
                    )
                )

            sample_records = await self._sample_repo.add_bulk(sample_records)

            for s, _rec in zip(samples, sample_records, strict=True):
                rel_path = f"{self._dataset_id}/{import_source.id}/{s.index}.txt"
                await self._store.put(
                    rel_path,
                    self._text_stream(s.text),
                )

            before_count = await self._sample_repo.count_active(self._dataset_id)
            after_count = before_count + len(sample_records)

            op = CurationOperation(
                dataset_id=self._dataset_id,
                operation_type="import",
                parameters=json.dumps(
                    {
                        "format": source_format,
                        "source": source_label,
                        "row_count": len(samples),
                    }
                ),
                sample_count_before=before_count,
                sample_count_after=after_count,
            )
            await self._op_repo.add(op)

            dataset.sample_count = after_count
            dataset.total_size_bytes = (dataset.total_size_bytes or 0) + sum(
                s.length for s in samples
            )
            dataset.curation_version = (dataset.curation_version or 0) + 1
            dataset.status = (
                DatasetStatus.READY if after_count > 0 else DatasetStatus.EMPTY
            )
            await self._dataset_repo.update(dataset)

            preview = [
                {"index": s.index, "text_preview": s.text[:200], "length": s.length}
                for s in samples[:20]
            ]

            await self._session.commit()

            return ImportResult(
                import_source_id=import_source.id,
                rows_imported=len(sample_records),
                errors=[],
                preview=preview,
            )
        except Exception:
            await self._session.rollback()
            dataset.status = (
                DatasetStatus.READY if dataset.sample_count > 0 else DatasetStatus.EMPTY
            )
            await self._dataset_repo.update(dataset)
            raise

    async def commit_corpus_import(self, docs: list[str]) -> ImportResult:
        """Import pre-chunked corpus documents, preserving each document as-is.

        Unlike the legacy join-then-split approach (which fragmented
        multi-line chunks), this delegates to
        :meth:`commit_docs_import` for byte-for-byte preservation of
        each document.

        Parameters
        ----------
        docs : list[str]
            Pre-chunked document strings to import.

        Returns
        -------
        ImportResult
            Outcome including import source ID, rows imported, errors,
            and preview.
        """
        return await self.commit_docs_import(
            docs=docs,
            source_label="corpus",
            source_format="corpus",
        )

    def _parse(
        self, text: str, fmt: str
    ) -> tuple[list[ParsedSample], list[dict[str, Any]]]:
        """Parse raw text into samples according to the format.

        Supports TXT, CSV, JSONL, JSON, paste, and corpus formats.
        Returns parsed samples and any errors encountered.

        Parameters
        ----------
        text : str
            The raw text to parse.
        fmt : str
            Input format identifier.

        Returns
        -------
        tuple[list[ParsedSample], list[dict]]
            Parsed samples and error dicts (each with ``"row"`` and
            ``"error"`` keys).
        """
        errors: list[dict[str, Any]] = []
        samples: list[ParsedSample] = []
        index = 0

        try:
            if fmt == "txt":
                for line in text.splitlines():
                    stripped = line.strip()
                    if stripped:
                        samples.append(ParsedSample(stripped, index))
                        index += 1
            elif fmt == "csv":
                reader = csv.reader(io.StringIO(text))
                for row in reader:
                    if row and row[0].strip():
                        samples.append(ParsedSample(row[0].strip(), index))
                        index += 1
            elif fmt == "jsonl":
                for line in text.splitlines():
                    stripped = line.strip()
                    if stripped:
                        try:
                            obj = json.loads(stripped)
                            if isinstance(obj, dict):
                                text_val = obj.get("text", obj.get("content", str(obj)))
                            else:
                                text_val = str(obj)
                            samples.append(ParsedSample(str(text_val).strip(), index))
                        except json.JSONDecodeError as e:
                            errors.append({"row": index, "error": str(e)})
                        index += 1
            elif fmt == "json":
                data = json.loads(text)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            text_val = item.get("text", item.get("content", str(item)))
                        else:
                            text_val = str(item)
                        samples.append(ParsedSample(str(text_val).strip(), index))
                        index += 1
                elif isinstance(data, str):
                    samples.append(ParsedSample(data.strip(), index))
            elif fmt == "paste":
                for line in text.splitlines():
                    stripped = line.strip()
                    if stripped:
                        samples.append(ParsedSample(stripped, index))
                        index += 1
            elif fmt == "corpus":
                for doc in text.split("\n"):
                    stripped = doc.strip()
                    if stripped:
                        samples.append(ParsedSample(stripped, index))
                        index += 1
        except Exception as e:  # pylint: disable=broad-exception-caught
            errors.append({"row": -1, "error": f"Parse error: {e}"})

        return samples, errors

    async def _text_stream(self, text: str) -> AsyncIterator[bytes]:
        """Async generator yielding UTF-8 encoded text as byte chunks.

        Parameters
        ----------
        text : str
            The text to encode.

        Yields
        ------
        bytes
            UTF-8 encoded text content.
        """
        yield text.encode("utf-8")
