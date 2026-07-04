"""Tests for fine-tune dataset and chat template API endpoints.

Covers /v1/chat-templates and /v1/fine-tune-datasets routes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from anvil.api.app import app
from anvil.api.deps import get_workbench
from anvil.services._shared.fine_tune_dataset_status import FineTuneDatasetStatus


@pytest.fixture
def mock_workbench():
    wb = MagicMock()
    wb._session = MagicMock()
    wb.dataset_repo = MagicMock()
    wb.dataset_repo.get = AsyncMock()
    wb.dataset_repo.get_active_for_dataset = AsyncMock()
    wb.dataset_repo.add = AsyncMock()
    wb.ftd_repo = MagicMock()
    wb.ftd_repo.get = AsyncMock()
    wb.ftd_repo.get_active_for_dataset = AsyncMock()
    wb.ftd_repo.get_all = AsyncMock()
    wb.ftd_repo.add = AsyncMock()
    return wb


@pytest.fixture
def override_dep(mock_workbench):
    app.dependency_overrides[get_workbench] = lambda: mock_workbench
    yield
    app.dependency_overrides.clear()


def _make_ftd(
    ftd_id: int = 1,
    dataset_id: int = 1,
    status: str = FineTuneDatasetStatus.READY,
) -> MagicMock:
    ftd = MagicMock()
    ftd.id = ftd_id
    ftd.dataset_id = dataset_id
    ftd.chat_template_id = None
    ftd.base_model_ref = None
    ftd.status = status
    ftd.record_type = "sft"
    ftd.record_count = 100
    ftd.summary_json = '{"total": 100, "succeeded": 95, "failed": 5, "errors": []}'
    ftd.created_at = datetime.now(UTC)
    ftd.updated_at = datetime.now(UTC)
    ftd.started_at = datetime.now(UTC)
    ftd.finished_at = datetime.now(UTC)
    return ftd


########################################################################
# Chat Template Endpoints
########################################################################


class TestCreateChatTemplate:
    """Tests for POST /v1/chat-templates."""

    async def test_create_success(self, client, mock_workbench, override_dep):
        """Returns 201 with created template metadata."""
        fake_template = MagicMock()
        fake_template.id = 1
        fake_template.name = "test-template"
        fake_template.tokenizer_family = "bpe"
        fake_template.status = "active"
        fake_template.created_at = datetime.now(UTC)

        # Mock the ChatTemplateService via the workbench's session
        mock_svc = AsyncMock()
        mock_svc.create.return_value = fake_template

        with (
            patch(
                "anvil.api.v1.fine_tune_datasets.ChatTemplateService",
                return_value=mock_svc,
            ),
        ):
            resp = await client.post(
                "/v1/chat-templates",
                json={
                    "name": "test-template",
                    "template_string": "{{ prompt }}",
                    "tokenizer_family": "bpe",
                },
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == 1
        assert data["name"] == "test-template"
        assert data["tokenizer_family"] == "bpe"

    async def test_create_duplicate_name(self, client, mock_workbench, override_dep):
        """Returns 409 when name already exists."""
        mock_svc = AsyncMock()
        mock_svc.create.side_effect = ValueError("Chat template 'test' already exists")

        with patch(
            "anvil.api.v1.fine_tune_datasets.ChatTemplateService",
            return_value=mock_svc,
        ):
            resp = await client.post(
                "/v1/chat-templates",
                json={
                    "name": "test",
                    "template_string": "{{ prompt }}",
                    "tokenizer_family": "bpe",
                },
            )

        assert resp.status_code == 409

    async def test_create_validates_fields(self, client, mock_workbench, override_dep):
        """Pydantic validation: missing fields return 422."""
        resp = await client.post("/v1/chat-templates", json={})
        assert resp.status_code == 422


class TestListChatTemplates:
    """Tests for GET /v1/chat-templates."""

    @staticmethod
    def _make_template(tid: int, name: str) -> MagicMock:
        t = MagicMock()
        t.id = tid
        t.name = name
        t.tokenizer_family = "bpe"
        t.status = "active"
        t.created_at = datetime.now(UTC)
        return t

    async def test_list_all(self, client, mock_workbench, override_dep):
        """Returns all chat templates."""
        mock_svc = AsyncMock()
        mock_svc.list_.return_value = [
            self._make_template(1, "template-a"),
            self._make_template(2, "template-b"),
        ]

        with patch(
            "anvil.api.v1.fine_tune_datasets.ChatTemplateService",
            return_value=mock_svc,
        ):
            resp = await client.get("/v1/chat-templates")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_with_filters(self, client, mock_workbench, override_dep):
        """Filters are forwarded to the service."""
        mock_svc = AsyncMock()
        mock_svc.list_.return_value = []

        with patch(
            "anvil.api.v1.fine_tune_datasets.ChatTemplateService",
            return_value=mock_svc,
        ):
            resp = await client.get(
                "/v1/chat-templates?tokenizer_family=bpe&status=active",
            )

        assert resp.status_code == 200
        mock_svc.list_.assert_called_with(
            tokenizer_family="bpe",
            status="active",
        )

    async def test_list_empty(self, client, mock_workbench, override_dep):
        """Returns empty list when no templates exist."""
        mock_svc = AsyncMock()
        mock_svc.list_.return_value = []

        with patch(
            "anvil.api.v1.fine_tune_datasets.ChatTemplateService",
            return_value=mock_svc,
        ):
            resp = await client.get("/v1/chat-templates")

        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["total"] == 0


########################################################################
# Fine-Tune Dataset Endpoints
########################################################################


class TestCreateFineTuneDataset:
    """Tests for POST /v1/fine-tune-datasets."""

    async def test_create_success(self, client, mock_workbench, override_dep):
        """Returns 202 with job metadata."""
        mock_workbench.dataset_repo.get.return_value = MagicMock(id=1)
        mock_workbench.ftd_repo.get_active_for_dataset.return_value = None
        mock_workbench.ftd_repo.add.return_value = _make_ftd(
            ftd_id=42, status=FineTuneDatasetStatus.PREPARING
        )

        resp = await client.post(
            "/v1/fine-tune-datasets",
            json={
                "dataset_id": 1,
                "record_type": "sft",
                "batch_size": 500,
            },
        )

        assert resp.status_code == 202
        data = resp.json()
        assert data["job_id"] == 42
        assert data["status"] == FineTuneDatasetStatus.PREPARING
        mock_workbench.dataset_repo.get.assert_awaited_with(1)

    async def test_create_source_dataset_not_found(
        self,
        client,
        mock_workbench,
        override_dep,
    ):
        """Returns 404 when source dataset does not exist."""
        mock_workbench.dataset_repo.get.return_value = None

        resp = await client.post(
            "/v1/fine-tune-datasets",
            json={"dataset_id": 999, "record_type": "sft"},
        )

        assert resp.status_code == 404
        assert "Dataset not found" in resp.json()["detail"]

    async def test_create_concurrent_preparation(
        self,
        client,
        mock_workbench,
        override_dep,
    ):
        """Returns 409 when a preparation is already active."""
        mock_workbench.dataset_repo.get.return_value = MagicMock(id=1)
        mock_workbench.ftd_repo.get_active_for_dataset.return_value = _make_ftd(
            ftd_id=7,
            status=FineTuneDatasetStatus.PREPARING,
        )

        resp = await client.post(
            "/v1/fine-tune-datasets",
            json={"dataset_id": 1, "record_type": "sft"},
        )

        assert resp.status_code == 409
        assert "already has an active preparation" in resp.json()["detail"]


class TestGetJobStatus:
    """Tests for GET /v1/fine-tune-datasets/jobs/{job_id}/status."""

    async def test_job_found(self, client, mock_workbench, override_dep):
        """Returns job status with summary."""
        mock_workbench.ftd_repo.get.return_value = _make_ftd(
            ftd_id=1,
            status=FineTuneDatasetStatus.READY,
        )

        resp = await client.get("/v1/fine-tune-datasets/jobs/1/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == 1
        assert data["status"] == FineTuneDatasetStatus.READY
        assert data["summary"] is not None
        assert data["summary"]["total"] == 100

    async def test_job_not_found(self, client, mock_workbench, override_dep):
        """Returns 404 when job does not exist."""
        mock_workbench.ftd_repo.get.return_value = None

        resp = await client.get("/v1/fine-tune-datasets/jobs/999/status")

        assert resp.status_code == 404
        assert "Job not found" in resp.json()["detail"]

    async def test_job_without_summary(self, client, mock_workbench, override_dep):
        """Returns None summary when no summary_json exists."""
        ftd = _make_ftd(status=FineTuneDatasetStatus.PREPARING)
        ftd.summary_json = None
        mock_workbench.ftd_repo.get.return_value = ftd

        resp = await client.get("/v1/fine-tune-datasets/jobs/1/status")

        assert resp.status_code == 200
        assert resp.json()["summary"] is None

    async def test_job_with_corrupted_summary(
        self, client, mock_workbench, override_dep
    ):
        """Returns None summary when summary_json is corrupted."""
        ftd = _make_ftd()
        ftd.summary_json = "not-valid-json"
        mock_workbench.ftd_repo.get.return_value = ftd

        resp = await client.get("/v1/fine-tune-datasets/jobs/1/status")

        assert resp.status_code == 200
        assert resp.json()["summary"] is None


class TestGetFineTuneDataset:
    """Tests for GET /v1/fine-tune-datasets/{ftd_id}."""

    async def test_get_found(self, client, mock_workbench, override_dep):
        """Returns serialized fine-tune dataset."""
        mock_workbench.ftd_repo.get.return_value = _make_ftd(ftd_id=5)

        resp = await client.get("/v1/fine-tune-datasets/5")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 5
        assert data["status"] == FineTuneDatasetStatus.READY
        assert data["record_count"] == 100

    async def test_get_not_found(self, client, mock_workbench, override_dep):
        """Returns 404 when fine-tune dataset not found."""
        mock_workbench.ftd_repo.get.return_value = None

        resp = await client.get("/v1/fine-tune-datasets/999")

        assert resp.status_code == 404
        assert "Fine-tune dataset not found" in resp.json()["detail"]


class TestListFineTuneDatasets:
    """Tests for GET /v1/fine-tune-datasets."""

    async def test_list_all(self, client, mock_workbench, override_dep):
        """Returns all fine-tune datasets."""
        mock_workbench.ftd_repo.get_all.return_value = [
            _make_ftd(ftd_id=1),
            _make_ftd(ftd_id=2),
        ]

        resp = await client.get("/v1/fine-tune-datasets")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_with_filters(self, client, mock_workbench, override_dep):
        """Filters are forwarded to repository."""
        mock_workbench.ftd_repo.get_all.return_value = []

        resp = await client.get(
            "/v1/fine-tune-datasets?dataset_id=1&status=ready&base_model_ref=5",
        )

        assert resp.status_code == 200
        mock_workbench.ftd_repo.get_all.assert_awaited_with(
            dataset_id=1,
            status="ready",
            base_model_ref=5,
        )

    async def test_list_empty(self, client, mock_workbench, override_dep):
        """Returns empty list."""
        mock_workbench.ftd_repo.get_all.return_value = []

        resp = await client.get("/v1/fine-tune-datasets")

        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["total"] == 0


class TestRetryFineTuneDataset:
    """Tests for POST /v1/fine-tune-datasets/{ftd_id}/retry."""

    async def test_retry_success(self, client, mock_workbench, override_dep):
        """Returns 202 with new job ID."""
        mock_workbench.ftd_repo.get.return_value = _make_ftd(
            ftd_id=1,
            status=FineTuneDatasetStatus.FAILED,
        )
        mock_workbench.ftd_repo.add.return_value = _make_ftd(
            ftd_id=42,
            status=FineTuneDatasetStatus.PREPARING,
        )

        resp = await client.post("/v1/fine-tune-datasets/1/retry")

        assert resp.status_code == 202
        data = resp.json()
        assert data["job_id"] == 42
        assert data["status"] == FineTuneDatasetStatus.PREPARING

    async def test_retry_not_found(self, client, mock_workbench, override_dep):
        """Returns 404 when fine-tune dataset not found."""
        mock_workbench.ftd_repo.get.return_value = None

        resp = await client.post("/v1/fine-tune-datasets/999/retry")

        assert resp.status_code == 404
        assert "Fine-tune dataset not found" in resp.json()["detail"]

    async def test_retry_not_failed(self, client, mock_workbench, override_dep):
        """Returns 409 when status is not 'failed'."""
        mock_workbench.ftd_repo.get.return_value = _make_ftd(
            ftd_id=1,
            status=FineTuneDatasetStatus.READY,
        )

        resp = await client.post("/v1/fine-tune-datasets/1/retry")

        assert resp.status_code == 409
        assert "Cannot retry" in resp.json()["detail"]
