# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for dataset management API endpoints (v1).

Covers the dataset CRUD, upload, export, samples, curation page,
and curation operation endpoints against a mocked workbench.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from anvil.api.app import app
from anvil.api.deps import get_workbench


def _make_mock_dataset(
    dataset_id: int,
    name: str = "test-dataset",
    description: str | None = "A test dataset",
    filename: str = "test.txt",
    sample_count: int = 100,
    total_size_bytes: int = 5000,
    status: str = "ready",
    curation_version: int = 0,
    vocabulary_size: int = 50,
    document_count: int = 100,
) -> MagicMock:
    """Build a MagicMock that looks like a Dataset ORM object.

    Parameters
    ----------
    dataset_id : int
        Primary key.
    name : str, optional
        Dataset name. Defaults to ``"test-dataset"``.
    description : str | None, optional
        Description. Defaults to ``"A test dataset"``.
    filename : str, optional
        Source filename. Defaults to ``"test.txt"``.
    sample_count : int, optional
        Number of samples. Defaults to ``100``.
    total_size_bytes : int, optional
        Total dataset size. Defaults to ``5000``.
    status : str, optional
        Processing status. Defaults to ``"ready"``.
    curation_version : int, optional
        Curation version. Defaults to ``0``.
    vocabulary_size : int, optional
        Unique token count. Defaults to ``50``.
    document_count : int, optional
        Number of documents. Defaults to ``100``.

    Returns
    -------
    MagicMock
        A mock dataset object compatible with ``_serialize``.
    """
    ds = MagicMock()
    ds.id = dataset_id
    ds.name = name
    ds.description = description
    ds.filename = filename
    ds.sample_count = sample_count
    ds.total_size_bytes = total_size_bytes
    ds.status = status
    ds.curation_version = curation_version
    ds.vocabulary_size = vocabulary_size
    ds.document_count = document_count
    ds.created_at = "2026-01-15 10:00:00"
    ds.updated_at = "2026-01-15 12:00:00"
    return ds


@pytest.fixture
def mock_workbench():
    """Create a fully mocked AnvilWorkbench for dataset endpoints."""
    wb = MagicMock()

    # ── DatasetService (workbench.datasets) ──────────────────────────────
    wb.datasets = MagicMock()
    wb.datasets.list_datasets = AsyncMock()
    wb.datasets.search_datasets = AsyncMock()
    wb.datasets.get_dataset = AsyncMock()
    wb.datasets.create_dataset = AsyncMock()
    wb.datasets.update_dataset = AsyncMock()
    wb.datasets.delete_dataset = AsyncMock()

    # ── DatasetRepository (workbench.dataset_repo) ────────────────────────
    wb.dataset_repo = MagicMock()
    wb.dataset_repo.get = AsyncMock()
    wb.dataset_repo.get_by_name = AsyncMock()

    # ── Factory services (sync call, returns mock with async methods) ────
    wb.dataset_curation = MagicMock()
    wb.dataset_import = MagicMock()
    wb.dataset_export = MagicMock()

    # ── Session ──────────────────────────────────────────────────────────
    wb.session = MagicMock()
    wb.session.commit = AsyncMock()
    wb.session.refresh = AsyncMock()

    # ── Audit ────────────────────────────────────────────────────────────
    wb.audit = MagicMock()
    wb.audit.record = AsyncMock()

    # ── Tracking ─────────────────────────────────────────────────────────
    wb.tracking = MagicMock()
    wb.tracking.is_degraded = False
    wb.tracking.log_dataset_lifecycle_event = AsyncMock()

    # ── Store (async generator) ──────────────────────────────────────────
    wb.store = MagicMock()
    wb.store.get = MagicMock()

    return wb


def _make_async_gen(*items: str) -> AsyncMock:
    """Build an async generator mock that yields *items.

    Parameters
    ----------
    *items : str
        Items to yield, one per iteration.

    Returns
    -------
    AsyncMock
        A callable mock that returns an async generator.
    """

    async def _gen() -> Any:  # type: ignore[misc]
        for item in items:
            yield item.encode("utf-8")

    return MagicMock(return_value=_gen())


def _make_string_gen(*items: str) -> MagicMock:
    """Build an async generator mock that yields *items as strings.

    Parameters
    ----------
    *items : str
        Items to yield as plain strings (not bytes).

    Returns
    -------
    MagicMock
        A callable mock that returns an async generator yielding strings.
    """

    async def _gen() -> Any:  # type: ignore[misc]
        for item in items:
            yield item

    return MagicMock(return_value=_gen())


@pytest.fixture
def override_dep(mock_workbench):
    """Override the ``get_workbench`` dependency with ``mock_workbench``."""
    app.dependency_overrides[get_workbench] = lambda: mock_workbench
    yield
    app.dependency_overrides.clear()


########################################################################
# GET /v1/datasets — list_datasets / search_datasets
########################################################################


class TestListDatasets:
    """Tests for GET /v1/datasets."""

    async def test_returns_all_datasets(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: list returns all datasets."""
        d1 = _make_mock_dataset(1, name="ds-a")
        d2 = _make_mock_dataset(2, name="ds-b")
        mock_workbench.datasets.list_datasets.return_value = [d1, d2]

        resp = await client.get("/v1/datasets")
        assert resp.status_code == 200
        body = resp.json()
        assert body["error"] is None
        datasets = body["data"]["datasets"]
        assert len(datasets) == 2
        assert datasets[0]["name"] == "ds-a"
        assert datasets[1]["name"] == "ds-b"
        mock_workbench.datasets.list_datasets.assert_awaited_once()

    async def test_empty_list(self, client, mock_workbench, override_dep):
        """Edge case: no datasets returns an empty list."""
        mock_workbench.datasets.list_datasets.return_value = []

        resp = await client.get("/v1/datasets")
        assert resp.status_code == 200
        assert resp.json()["data"]["datasets"] == []

    async def test_search_by_query(
        self, client, mock_workbench, override_dep
    ):
        """When ``q`` is provided, delegates to search_datasets."""
        d1 = _make_mock_dataset(1, name="search-hit")
        mock_workbench.datasets.search_datasets.return_value = [d1]

        resp = await client.get("/v1/datasets", params={"q": "search"})
        assert resp.status_code == 200
        assert len(resp.json()["data"]["datasets"]) == 1
        mock_workbench.datasets.search_datasets.assert_awaited_once_with(
            "search"
        )
        mock_workbench.datasets.list_datasets.assert_not_awaited()


########################################################################
# POST /v1/datasets — create_dataset
########################################################################


class TestCreateDataset:
    """Tests for POST /v1/datasets."""

    async def test_creates_successfully(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: dataset created with name and description."""
        new_ds = _make_mock_dataset(1, name="my-ds", description="My dataset")
        mock_workbench.datasets.create_dataset.return_value = new_ds

        resp = await client.post(
            "/v1/datasets",
            json={"name": "my-ds", "description": "My dataset"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["name"] == "my-ds"
        assert body["data"]["description"] == "My dataset"
        assert body["error"] is None
        mock_workbench.datasets.create_dataset.assert_awaited_once_with(
            "my-ds", "My dataset"
        )

    async def test_creates_without_description(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: description is optional."""
        new_ds = _make_mock_dataset(2, name="minimal")
        mock_workbench.datasets.create_dataset.return_value = new_ds

        resp = await client.post(
            "/v1/datasets", json={"name": "minimal"}
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "minimal"
        mock_workbench.datasets.create_dataset.assert_awaited_once_with(
            "minimal", None
        )

    async def test_rejects_empty_name(
        self, client, mock_workbench, override_dep
    ):
        """Validation: empty name returns 422."""
        resp = await client.post(
            "/v1/datasets", json={"name": "   "}
        )
        assert resp.status_code == 422
        assert "empty" in resp.json()["detail"].lower()
        mock_workbench.datasets.create_dataset.assert_not_awaited()


########################################################################
# GET /v1/datasets/{id} — get_dataset
########################################################################


class TestGetDataset:
    """Tests for GET /v1/datasets/{id}."""

    async def test_returns_dataset(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: existing dataset returned."""
        ds = _make_mock_dataset(42, name="target-ds")
        mock_workbench.datasets.get_dataset.return_value = ds

        resp = await client.get("/v1/datasets/42")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == 42
        assert body["data"]["name"] == "target-ds"
        assert body["error"] is None

    async def test_returns_404_when_not_found(
        self, client, mock_workbench, override_dep
    ):
        """Error: missing dataset returns 404."""
        mock_workbench.datasets.get_dataset.return_value = None

        resp = await client.get("/v1/datasets/999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


########################################################################
# PUT /v1/datasets/{id} — update_dataset
########################################################################


class TestUpdateDataset:
    """Tests for PUT /v1/datasets/{id}."""

    async def test_updates_name_and_description(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: updates both name and description."""
        updated = _make_mock_dataset(1, name="new-name", description="new desc")
        mock_workbench.datasets.update_dataset.return_value = updated

        resp = await client.put(
            "/v1/datasets/1",
            json={"name": "new-name", "description": "new desc"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "new-name"
        mock_workbench.datasets.update_dataset.assert_awaited_once_with(
            1, name="new-name", description="new desc"
        )

    async def test_updates_name_only(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: only name supplied."""
        updated = _make_mock_dataset(1, name="only-name")
        mock_workbench.datasets.update_dataset.return_value = updated

        resp = await client.put(
            "/v1/datasets/1", json={"name": "only-name"}
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "only-name"

    async def test_returns_404_when_not_found(
        self, client, mock_workbench, override_dep
    ):
        """Error: missing dataset returns 404."""
        mock_workbench.datasets.update_dataset.return_value = None

        resp = await client.put(
            "/v1/datasets/999",
            json={"name": "ghost"},
        )
        assert resp.status_code == 404


########################################################################
# DELETE /v1/datasets/{id} — delete_dataset
########################################################################


class TestDeleteDataset:
    """Tests for DELETE /v1/datasets/{id}."""

    async def test_deletes_successfully(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: dataset deleted, lifecycle event logged."""
        ds = _make_mock_dataset(1, name="delete-me")
        mock_workbench.datasets.get_dataset.return_value = ds
        mock_workbench.datasets.delete_dataset = AsyncMock()

        resp = await client.delete("/v1/datasets/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["message"] == "Dataset deleted"
        mock_workbench.datasets.delete_dataset.assert_awaited_once_with(
            1, audit=mock_workbench.audit
        )

    async def test_returns_404_when_not_found(
        self, client, mock_workbench, override_dep
    ):
        """Error: missing dataset returns 404."""
        mock_workbench.datasets.get_dataset.return_value = None

        resp = await client.delete("/v1/datasets/999")
        assert resp.status_code == 404

    async def test_blocks_demo_deletion_without_force(
        self, client, mock_workbench, override_dep
    ):
        """Error: demo dataset blocked without force=true."""
        ds = _make_mock_dataset(1, name="Demo - Sample")
        mock_workbench.datasets.get_dataset.return_value = ds

        resp = await client.delete("/v1/datasets/1")
        assert resp.status_code == 409
        assert "demo" in resp.json()["detail"].lower()

    async def test_deletes_demo_with_force(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: demo dataset deleted with force=true."""
        ds = _make_mock_dataset(1, name="Demo - Sample")
        mock_workbench.datasets.get_dataset.return_value = ds
        mock_workbench.datasets.delete_dataset = AsyncMock()

        resp = await client.delete("/v1/datasets/1?force=true")
        assert resp.status_code == 200
        assert resp.json()["data"]["message"] == "Dataset deleted"

    async def test_handles_value_error_on_delete(
        self, client, mock_workbench, override_dep
    ):
        """Error: ValueError from delete_dataset becomes 409."""
        ds = _make_mock_dataset(1, name="referenced")
        mock_workbench.datasets.get_dataset.return_value = ds
        mock_workbench.datasets.delete_dataset = AsyncMock(
            side_effect=ValueError("Training configs reference it")
        )

        resp = await client.delete("/v1/datasets/1")
        assert resp.status_code == 409


########################################################################
# POST /v1/datasets/upload — upload_dataset
########################################################################


class TestUploadDataset:
    """Tests for POST /v1/datasets/upload."""

    async def test_upload_successfully(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: file uploaded and dataset created."""
        ds = _make_mock_dataset(
            1,
            name="hello.txt",
            filename="hello.txt",
            sample_count=2,
            vocabulary_size=7,
        )
        mock_workbench.datasets.create_dataset.return_value = ds

        resp = await client.post(
            "/v1/datasets/upload",
            files={"file": ("hello.txt", b"hello world\nfoo bar", "text/plain")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["name"] == "hello.txt"
        assert body["error"] is None
        mock_workbench.datasets.create_dataset.assert_awaited_once()
        mock_workbench.session.commit.assert_awaited_once()
        mock_workbench.session.refresh.assert_awaited_once_with(ds)
        mock_workbench.audit.record.assert_awaited_once()

    async def test_upload_empty_file(
        self, client, mock_workbench, override_dep
    ):
        """Edge case: empty file results in zero samples."""
        ds = _make_mock_dataset(
            2, name="empty.txt", filename="empty.txt",
            sample_count=0, vocabulary_size=0, document_count=0,
        )
        mock_workbench.datasets.create_dataset.return_value = ds

        resp = await client.post(
            "/v1/datasets/upload",
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["sample_count"] == 0

    async def test_upload_untitled_for_missing_filename(
        self, client, mock_workbench, override_dep
    ):
        """Edge case: file without filename defaults to 'untitled'."""
        ds = _make_mock_dataset(3, name="untitled")
        mock_workbench.datasets.create_dataset.return_value = ds

        resp = await client.post(
            "/v1/datasets/upload",
            files={"file": b"content"},
        )
        assert resp.status_code == 200
        mock_workbench.datasets.create_dataset.assert_awaited()


########################################################################
# GET /v1/datasets/{id}/export — export_dataset
########################################################################


class TestExportDataset:
    """Tests for GET /v1/datasets/{id}/export."""

    async def test_export_txt(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: export as txt."""
        export_svc = MagicMock()
        export_svc.export_txt = _make_string_gen("line1\n", "line2\n")
        mock_workbench.dataset_export.return_value = export_svc

        resp = await client.get("/v1/datasets/1/export", params={"format": "txt"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")
        assert "attachment" in resp.headers["content-disposition"]
        assert resp.text == "line1\nline2\n"

    async def test_export_csv(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: export as csv."""
        export_svc = MagicMock()
        export_svc.export_csv = _make_string_gen("a,b\n", "1,2\n")
        mock_workbench.dataset_export.return_value = export_svc

        resp = await client.get("/v1/datasets/1/export", params={"format": "csv"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")

    async def test_export_jsonl(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: export as jsonl."""
        export_svc = MagicMock()
        export_svc.export_jsonl = _make_string_gen('{"a":1}\n', '{"b":2}\n')
        mock_workbench.dataset_export.return_value = export_svc

        resp = await client.get("/v1/datasets/1/export", params={"format": "jsonl"})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/x-ndjson"

    async def test_export_unsupported_format(
        self, client, mock_workbench, override_dep
    ):
        """Error: unsupported format returns 422."""
        resp = await client.get(
            "/v1/datasets/1/export", params={"format": "xml"}
        )
        assert resp.status_code == 422
        assert "unsupported" in resp.json()["detail"].lower()


########################################################################
# GET /v1/datasets/{id}/samples — list_samples
########################################################################


class TestListSamples:
    """Tests for GET /v1/datasets/{id}/samples."""

    async def test_returns_paginated_samples(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: paginated samples returned."""
        curation_svc = MagicMock()
        sample = MagicMock()
        sample.id = 10
        sample.index = 0
        sample.length = 13
        sample.content_hash = "abc123"
        sample.file_path = "samples/10.txt"
        curation_svc.get_active_samples = AsyncMock(
            return_value=([sample], 1)
        )
        mock_workbench.dataset_curation.return_value = curation_svc

        # Mock store.get to return content bytes
        mock_workbench.store.get = _make_async_gen("hello world!!")

        resp = await client.get("/v1/datasets/1/samples")
        assert resp.status_code == 200
        body = resp.json()
        assert body["error"] is None
        assert body["data"]["total"] == 1
        assert body["data"]["offset"] == 0
        assert body["data"]["limit"] == 50
        assert len(body["data"]["samples"]) == 1
        assert body["data"]["samples"][0]["id"] == 10
        assert body["data"]["samples"][0]["text_preview"] == "hello world!!"

    async def test_respects_offset_and_limit(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: passes offset/limit/search to service."""
        curation_svc = MagicMock()
        curation_svc.get_active_samples = AsyncMock(return_value=([], 0))
        mock_workbench.dataset_curation.return_value = curation_svc
        mock_workbench.store.get = _make_async_gen("")

        resp = await client.get(
            "/v1/datasets/1/samples",
            params={"offset": "10", "limit": "5", "search": "foo"},
        )
        assert resp.status_code == 200
        curation_svc.get_active_samples.assert_awaited_once_with(
            10, 5, "foo"
        )

    async def test_truncates_preview_to_200_chars(
        self, client, mock_workbench, override_dep
    ):
        """Edge case: text preview truncated to 200 chars."""
        curation_svc = MagicMock()
        sample = MagicMock()
        sample.id = 1
        sample.index = 0
        sample.length = 500
        sample.content_hash = "xyz"
        sample.file_path = "samples/1.txt"
        curation_svc.get_active_samples = AsyncMock(
            return_value=([sample], 1)
        )
        mock_workbench.dataset_curation.return_value = curation_svc
        mock_workbench.store.get = _make_async_gen("x" * 500)

        resp = await client.get("/v1/datasets/1/samples")
        assert resp.status_code == 200
        preview = resp.json()["data"]["samples"][0]["text_preview"]
        assert len(preview) == 200


########################################################################
# GET /v1/datasets/{id}/curate — curate_dataset_page
########################################################################


class TestCuratePage:
    """Tests for GET /v1/datasets/{id}/curate."""

    async def test_renders_curation_page(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: renders curation template for existing dataset."""
        ds = _make_mock_dataset(1, name="curatable")
        mock_workbench.dataset_repo.get.return_value = ds

        resp = await client.get("/v1/datasets/1/curate")
        assert resp.status_code == 200

    async def test_returns_404_when_not_found(
        self, client, mock_workbench, override_dep
    ):
        """Error: missing dataset returns 404."""
        mock_workbench.dataset_repo.get.return_value = None

        resp = await client.get("/v1/datasets/999/curate")
        assert resp.status_code == 404


########################################################################
# POST /v1/datasets/{id}/curate/dedup — curate_dedup
########################################################################


class TestCurateDedup:
    """Tests for POST /v1/datasets/{id}/curate/dedup."""

    async def test_deduplicates_successfully(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: dedup operation completes."""
        curation_svc = MagicMock()
        result = MagicMock()
        result.operation_id = "op-1"
        result.samples_removed = 10
        result.samples_before = 100
        result.samples_after = 90
        curation_svc.deduplicate = AsyncMock(return_value=result)
        mock_workbench.dataset_curation.return_value = curation_svc

        resp = await client.post("/v1/datasets/1/curate/dedup")
        assert resp.status_code == 200
        body = resp.json()
        assert body["error"] is None
        assert body["data"]["samples_removed"] == 10
        assert body["data"]["samples_before"] == 100
        assert body["data"]["samples_after"] == 90
        curation_svc.deduplicate.assert_awaited_once()

    async def test_returns_404_on_value_error(
        self, client, mock_workbench, override_dep
    ):
        """Error: ValueError becomes 404."""
        curation_svc = MagicMock()
        curation_svc.deduplicate = AsyncMock(
            side_effect=ValueError("Dataset not found")
        )
        mock_workbench.dataset_curation.return_value = curation_svc

        resp = await client.post("/v1/datasets/999/curate/dedup")
        assert resp.status_code == 404

    async def test_dedup_logs_lifecycle_event(
        self, client, mock_workbench, override_dep
    ):
        """Tracking: lifecycle event logged after dedup."""
        curation_svc = MagicMock()
        result = MagicMock()
        result.operation_id = "op-1"
        result.samples_removed = 5
        result.samples_before = 50
        result.samples_after = 45
        curation_svc.deduplicate = AsyncMock(return_value=result)
        mock_workbench.dataset_curation.return_value = curation_svc
        mock_workbench.tracking.log_dataset_lifecycle_event = AsyncMock()

        await client.post("/v1/datasets/1/curate/dedup")
        mock_workbench.tracking.log_dataset_lifecycle_event.assert_awaited()


########################################################################
# POST /v1/datasets/{id}/curate/filter — curate_filter
########################################################################


class TestCurateFilter:
    """Tests for POST /v1/datasets/{id}/curate/filter."""

    async def test_filters_by_length(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: filter by min/max length."""
        curation_svc = MagicMock()
        result = MagicMock()
        result.operation_id = "op-2"
        result.samples_removed = 30
        result.samples_before = 100
        result.samples_after = 70
        curation_svc.filter_by_length = AsyncMock(return_value=result)
        mock_workbench.dataset_curation.return_value = curation_svc

        resp = await client.post(
            "/v1/datasets/1/curate/filter",
            json={"min_length": 10, "max_length": 500},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["samples_removed"] == 30
        curation_svc.filter_by_length.assert_awaited_once_with(10, 500)

    async def test_filter_no_bounds(
        self, client, mock_workbench, override_dep
    ):
        """Edge case: filter with no bounds (both None)."""
        curation_svc = MagicMock()
        result = MagicMock()
        result.operation_id = "op-3"
        result.samples_removed = 0
        result.samples_before = 50
        result.samples_after = 50
        curation_svc.filter_by_length = AsyncMock(return_value=result)
        mock_workbench.dataset_curation.return_value = curation_svc

        resp = await client.post(
            "/v1/datasets/1/curate/filter",
            json={},
        )
        assert resp.status_code == 200

    async def test_returns_404_on_value_error(
        self, client, mock_workbench, override_dep
    ):
        """Error: ValueError becomes 404."""
        curation_svc = MagicMock()
        curation_svc.filter_by_length = AsyncMock(
            side_effect=ValueError("Dataset not found")
        )
        mock_workbench.dataset_curation.return_value = curation_svc

        resp = await client.post(
            "/v1/datasets/999/curate/filter",
            json={"min_length": 1},
        )
        assert resp.status_code == 404


########################################################################
# POST /v1/datasets/{id}/curate/replace — curate_replace
########################################################################


class TestCurateReplace:
    """Tests for POST /v1/datasets/{id}/curate/replace."""

    async def test_regex_replace(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: regex replace operation."""
        curation_svc = MagicMock()
        curation_svc.regex_replace = AsyncMock(
            return_value={
                "operation_id": "op-4",
                "samples_affected": 20,
                "samples_before": 100,
                "samples_after": 100,
            }
        )
        mock_workbench.dataset_curation.return_value = curation_svc

        resp = await client.post(
            "/v1/datasets/1/curate/replace",
            json={"pattern": "foo", "replacement": "bar"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["operation_id"] == "op-4"
        assert body["data"]["samples_affected"] == 20
        curation_svc.regex_replace.assert_awaited_once_with(
            "foo", "bar", True
        )

    async def test_case_insensitive(
        self, client, mock_workbench, override_dep
    ):
        """Happy path: case-insensitive replace."""
        curation_svc = MagicMock()
        curation_svc.regex_replace = AsyncMock(
            return_value={
                "operation_id": "op-5",
                "samples_affected": 5,
                "samples_before": 50,
                "samples_after": 50,
            }
        )
        mock_workbench.dataset_curation.return_value = curation_svc

        resp = await client.post(
            "/v1/datasets/1/curate/replace",
            json={"pattern": "foo", "replacement": "bar", "case_sensitive": False},
        )
        assert resp.status_code == 200
        curation_svc.regex_replace.assert_awaited_once_with(
            "foo", "bar", False
        )

    async def test_returns_404_on_value_error(
        self, client, mock_workbench, override_dep
    ):
        """Error: ValueError becomes 404."""
        curation_svc = MagicMock()
        curation_svc.regex_replace = AsyncMock(
            side_effect=ValueError("Dataset not found")
        )
        mock_workbench.dataset_curation.return_value = curation_svc

        resp = await client.post(
            "/v1/datasets/999/curate/replace",
            json={"pattern": "x", "replacement": "y"},
        )
        assert resp.status_code == 404
