"""Unit tests for DatasetExportService — TXT, CSV, JSONL export formats."""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator

import pytest

from anvil.services.datasets.dataset_export import DatasetExportService


class _BytesStream:
    """Async iterable that yields a single bytes chunk."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._consumed = False

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self

    async def __anext__(self) -> bytes:
        if self._consumed:
            raise StopAsyncIteration
        self._consumed = True
        return self._data


class TestExportService:
    """Service-level export tests with in-memory DB and file store."""

    def test_service_instantiation(self):
        """DatasetExportService should expose all export methods."""
        assert hasattr(DatasetExportService, "export_txt")
        assert hasattr(DatasetExportService, "export_csv")
        assert hasattr(DatasetExportService, "export_jsonl")

    async def test_export_txt_format(self, tmp_path_factory, in_memory_session):
        """export_txt should yield each sample followed by a newline."""
        from anvil.db.models.dataset import Dataset
        from anvil.db.models.sample import Sample
        from anvil.storage.local import LocalFileStore

        store_root = tmp_path_factory.mktemp("store_root")
        store = LocalFileStore(str(store_root))

        ds = Dataset(name="export-test", filename="export.txt", file_path=str(store_root / "data.txt"))
        in_memory_session.add(ds)
        await in_memory_session.flush()
        await in_memory_session.refresh(ds)

        await store.put("samples/0.txt", _BytesStream(b"hello export"))  # NOSONAR
        sample = Sample(
            dataset_id=ds.id,
            index=0,
            content_hash=hashlib.sha256(b"hello export").hexdigest(),
            length=12,
            file_path="samples/0.txt",
            is_removed=False,
        )
        in_memory_session.add(sample)
        await in_memory_session.commit()

        svc = DatasetExportService(in_memory_session, ds.id, store=store)
        lines = [line async for line in svc.export_txt()]
        assert "hello export" in lines[0]

    async def test_export_csv_includes_header(self, tmp_path_factory, in_memory_session):
        """export_csv should include a header row and data rows."""
        from anvil.db.models.dataset import Dataset
        from anvil.db.models.sample import Sample
        from anvil.storage.local import LocalFileStore

        store_root = tmp_path_factory.mktemp("csv_root")
        store = LocalFileStore(str(store_root))

        ds = Dataset(name="csv-test", filename="csv.txt", file_path=str(store_root / "csv.txt"))
        in_memory_session.add(ds)
        await in_memory_session.flush()
        await in_memory_session.refresh(ds)

        await store.put("samples/0.txt", _BytesStream(b"csv data"))  # NOSONAR
        sample = Sample(
            dataset_id=ds.id,
            index=0,
            content_hash=hashlib.sha256(b"csv data").hexdigest(),
            length=8,
            file_path="samples/0.txt",
            is_removed=False,
        )
        in_memory_session.add(sample)
        await in_memory_session.commit()

        svc = DatasetExportService(in_memory_session, ds.id, store=store)
        lines = [line async for line in svc.export_csv()]
        assert "index,text" in lines[0]
        assert "csv data" in lines[1]

    async def test_export_jsonl_format(self, tmp_path_factory, in_memory_session):
        """export_jsonl should yield one JSON object per line."""
        from anvil.db.models.dataset import Dataset
        from anvil.db.models.sample import Sample
        from anvil.storage.local import LocalFileStore

        store_root = tmp_path_factory.mktemp("jsonl_root")
        store = LocalFileStore(str(store_root))

        ds = Dataset(name="jsonl-test", filename="jsonl.txt", file_path=str(store_root / "jsonl.txt"))
        in_memory_session.add(ds)
        await in_memory_session.flush()
        await in_memory_session.refresh(ds)

        await store.put("samples/0.txt", _BytesStream(b"jsonl data"))  # NOSONAR
        sample = Sample(
            dataset_id=ds.id,
            index=7,
            content_hash=hashlib.sha256(b"jsonl data").hexdigest(),
            length=10,
            file_path="samples/0.txt",
            is_removed=False,
        )
        in_memory_session.add(sample)
        await in_memory_session.commit()

        svc = DatasetExportService(in_memory_session, ds.id, store=store)
        lines = [line async for line in svc.export_jsonl()]
        parsed = json.loads(lines[0])
        assert parsed["index"] == 7
        assert parsed["text"] == "jsonl data"

    async def test_export_empty_dataset(self, tmp_path_factory, in_memory_session):
        """Exporting an empty dataset should yield no lines."""
        from anvil.db.models.dataset import Dataset

        store_root = tmp_path_factory.mktemp("empty")
        ds = Dataset(name="empty", filename="empty.txt", file_path=str(store_root / "empty.txt"))
        in_memory_session.add(ds)
        await in_memory_session.commit()

        svc = DatasetExportService(in_memory_session, ds.id)
        txt_lines = [l async for l in svc.export_txt()]
        assert txt_lines == []