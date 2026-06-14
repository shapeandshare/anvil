import csv
import hashlib
import io
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.curation import CurationOperation, ImportSource, Sample
from anvil.db.repositories.curation import (
    CurationOperationRepository,
    ImportSourceRepository,
    SampleRepository,
)
from anvil.db.repositories.datasets import DatasetRepository
from anvil.storage.local import LocalFileStore


class ImportResult:
    def __init__(
        self,
        import_source_id: int,
        rows_imported: int,
        errors: list[dict],
        preview: list[dict],
    ):
        self.import_source_id = import_source_id
        self.rows_imported = rows_imported
        self.errors = errors
        self.preview = preview


class ParsedSample:
    def __init__(self, text: str, index: int):
        self.text = text
        self.index = index
        self.content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.length = len(text)


class DatasetImportService:
    def __init__(
        self,
        session: AsyncSession,
        dataset_id: int,
        store: LocalFileStore | None = None,
    ):
        self._session = session
        self._dataset_id = dataset_id
        self._store = store or LocalFileStore("data/datasets")
        self._sample_repo = SampleRepository(session)
        self._op_repo = CurationOperationRepository(session)
        self._import_repo = ImportSourceRepository(session)
        self._dataset_repo = DatasetRepository(session)

    async def preview_import(
        self, text: str | None = None, fmt: str = "txt", max_rows: int = 20
    ) -> tuple[list[dict], list[dict]]:
        samples, errors = self._parse(text or "", fmt)
        preview = [
            {"index": s.index, "text_preview": s.text[:200], "length": s.length}
            for s in samples[:max_rows]
        ]
        return preview, errors

    async def commit_import(
        self, text: str, fmt: str = "txt"
    ) -> ImportResult:
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

        dataset.status = "importing"
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

            for s, rec in zip(samples, sample_records):
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
            dataset.status = "ready" if after_count > 0 else "empty"
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
            dataset.status = "ready" if dataset.sample_count > 0 else "empty"
            await self._dataset_repo.update(dataset)
            raise

    async def commit_corpus_import(self, docs: list[str]) -> ImportResult:
        text = "\n".join(docs)
        return await self.commit_import(text, fmt="corpus")

    def _parse(self, text: str, fmt: str) -> tuple[list[ParsedSample], list[dict]]:
        errors: list[dict] = []
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
        except Exception as e:
            errors.append({"row": -1, "error": f"Parse error: {e}"})

        return samples, errors

    async def _text_stream(self, text: str) -> AsyncIterator[bytes]:
        yield text.encode("utf-8")