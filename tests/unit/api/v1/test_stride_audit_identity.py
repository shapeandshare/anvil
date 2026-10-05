# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for STRIDE R-001/R-002/R-003 — actor identity in audit records.

Verifies that:
- R-001: training start and training stop emit audit records.
- R-002: corpus delete, model archive, and experiment delete emit audit records.
- R-003: audit records carry the authenticated request identity, not "system".

All tests use the ``client`` fixture (in-memory SQLite, API-key auth via
``X-API-Key`` header) and mock the service layer so no real training,
MLflow, or filesystem I/O runs.  The ``client`` fixture sends
``X-API-Key: <key>`` on every request, so ``get_actor_from_request``
returns ``"api_key"`` — the stable identity for API-key-authenticated calls.

Placement: ``tests/unit/api/v1/`` — uses the root ``tests/conftest.py``
``client`` fixture (same ``async_engine`` the app writes to).
Run directly: ``.venv/bin/pytest tests/unit/api/v1/test_stride_audit_identity.py -v``
"""

from __future__ import annotations

import contextlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.api.app import app
from anvil.api.deps import get_workbench
from anvil.api.v1 import training as training_module
from anvil.gpu import GpuInfo
from anvil.services.compute.training_engine import TrainingEngine
from anvil.services.governance.audit_action import AuditAction
from anvil.services.governance.audit_target_type import AuditTargetType
from anvil.services.tracking.tracking import TrackingService
from anvil.services.training.training_run_service import TrainingRunService

pytestmark = pytest.mark.asyncio

####################################################################
# Helpers
####################################################################


def _make_training_config() -> dict:
    """Return a minimal valid training config dict."""
    return {
        "n_layer": 1,
        "n_embd": 16,
        "n_head": 4,
        "block_size": 16,
        "num_steps": 1,
        "learning_rate": 0.01,
    }


def _training_patches():
    """Return an ExitStack with all patches needed to prevent real training.

    Mirrors the ``_default_patches`` helper in ``test_training.py``.
    Use as a plain context manager: ``with _training_patches(): ...``
    """
    mock_svc = MagicMock()
    mock_svc.reserve_run.return_value = 42
    mock_svc.allocate_experiment_id = AsyncMock(return_value=99)
    mock_svc.store_run_metadata = MagicMock()
    mock_svc.get_queue.return_value = None
    mock_svc.stop_run = MagicMock()

    mock_tracking = MagicMock()
    mock_tracking.start_run = AsyncMock(return_value="mlflow_1")
    mock_tracking.set_tag = AsyncMock()
    mock_tracking.log_metric = AsyncMock()
    mock_tracking.finish_run = AsyncMock()
    mock_tracking.fail_run = AsyncMock()
    mock_tracking.log_final_metric = AsyncMock()
    mock_tracking.log_dataset_input = AsyncMock()
    mock_tracking.log_corpus_input = AsyncMock()
    mock_tracking.register_source_model = AsyncMock()
    mock_tracking.is_degraded = False

    stack = contextlib.ExitStack()
    stack.enter_context(patch.object(training_module, "svc", mock_svc))
    stack.enter_context(patch.object(training_module, "tracking_svc", mock_tracking))
    stack.enter_context(
        patch(
            "anvil.services.training.training_run_service.resolve_backend",
            return_value={"engine": TrainingEngine.STDLIB, "device": "cpu"},
        )
    )
    stack.enter_context(
        patch(
            "anvil.services.training.training_run_service.detect_gpu",
            return_value=GpuInfo(available=False),
        )
    )
    stack.enter_context(
        patch.object(
            TrainingRunService,
            "_setup_mlflow_run",
            new=AsyncMock(return_value=("mlflow_1", 99)),
        )
    )
    stack.enter_context(
        patch.object(
            TrainingRunService,
            "_log_dataset_metadata",
            new=AsyncMock(),
        )
    )
    return stack


def _make_workbench_with_audit() -> MagicMock:
    """Return a minimal mock workbench with a working audit service."""
    wb = MagicMock()
    wb.audit = MagicMock()
    wb.audit.record = AsyncMock()
    wb.session = MagicMock()
    wb.session.commit = AsyncMock()
    return wb


####################################################################
# R-001: training start — audit record emitted
####################################################################


class TestTrainingStartAudit:
    """POST /v1/training/start must emit an audit record (R-001)."""

    async def test_start_training_emits_audit_record(self, client):
        """Audit record with action_type=training_start is created."""
        with _training_patches():
            resp = await client.post("/v1/training/start", json=_make_training_config())
        assert resp.status_code == 200

        from anvil.db.repositories.audit_events import AuditEventRepository
        from anvil.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            repo = AuditEventRepository(session)
            events = await repo.query(
                action_type=AuditAction.TRAINING_START.value, limit=10
            )
        assert len(events) >= 1, "Expected at least one training_start audit event"

    async def test_start_training_audit_actor_is_api_key(self, client):
        """Audit record actor is 'api_key' (not 'system') for API-key auth (R-003)."""
        with _training_patches():
            await client.post("/v1/training/start", json=_make_training_config())

        from anvil.db.repositories.audit_events import AuditEventRepository
        from anvil.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            repo = AuditEventRepository(session)
            events = await repo.query(
                action_type=AuditAction.TRAINING_START.value, limit=10
            )
        assert events, "Expected at least one training_start audit event"
        assert (
            events[-1].actor == "api_key"
        ), f"Expected actor='api_key', got {events[-1].actor!r}"

    async def test_start_training_audit_target_type(self, client):
        """Audit record target_type is 'training_run'."""
        with _training_patches():
            await client.post("/v1/training/start", json=_make_training_config())

        from anvil.db.repositories.audit_events import AuditEventRepository
        from anvil.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            repo = AuditEventRepository(session)
            events = await repo.query(
                action_type=AuditAction.TRAINING_START.value, limit=10
            )
        assert events
        assert events[-1].target_type == AuditTargetType.TRAINING_RUN.value


####################################################################
# R-001: training stop — audit record emitted
####################################################################


class TestTrainingStopAudit:
    """POST /v1/training/{run_id}/stop must emit an audit record (R-001)."""

    async def test_stop_training_emits_audit_record(self, client):
        """Audit record with action_type=training_stop is created."""
        with (
            patch.object(training_module.svc, "get_queue", return_value=None),
            patch.object(training_module.svc, "stop_run"),
        ):
            resp = await client.post("/v1/training/1/stop")
        assert resp.status_code == 200

        from anvil.db.repositories.audit_events import AuditEventRepository
        from anvil.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            repo = AuditEventRepository(session)
            events = await repo.query(
                action_type=AuditAction.TRAINING_STOP.value, limit=10
            )
        assert len(events) >= 1, "Expected at least one training_stop audit event"

    async def test_stop_training_audit_actor_is_api_key(self, client):
        """Audit record actor is 'api_key' (not 'system') for API-key auth (R-003)."""
        with (
            patch.object(training_module.svc, "get_queue", return_value=None),
            patch.object(training_module.svc, "stop_run"),
        ):
            await client.post("/v1/training/1/stop")

        from anvil.db.repositories.audit_events import AuditEventRepository
        from anvil.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            repo = AuditEventRepository(session)
            events = await repo.query(
                action_type=AuditAction.TRAINING_STOP.value, limit=10
            )
        assert events
        assert (
            events[-1].actor == "api_key"
        ), f"Expected actor='api_key', got {events[-1].actor!r}"


####################################################################
# R-002: corpus delete — audit record emitted
####################################################################


class TestCorpusDeleteAudit:
    """DELETE /v1/corpora/{id} must emit an audit record (R-002)."""

    async def test_corpus_delete_emits_audit_record(self, client, tmp_path):
        """Audit record with action_type=delete, target_type=corpus is created."""
        (tmp_path / "f.txt").write_text("data\n")
        create_r = await client.post(
            "/v1/corpora",
            json={"name": "stride-audit-corpus", "root_path": str(tmp_path)},
        )
        assert create_r.status_code == 200
        corpus_id = create_r.json()["data"]["id"]

        del_r = await client.delete(f"/v1/corpora/{corpus_id}")
        assert del_r.status_code == 200

        from anvil.db.repositories.audit_events import AuditEventRepository
        from anvil.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            repo = AuditEventRepository(session)
            events = await repo.query(
                action_type=AuditAction.DELETE.value,
                target_type=AuditTargetType.CORPUS.value,
                limit=10,
            )
        assert len(events) >= 1, "Expected at least one corpus delete audit event"
        assert events[-1].target_id == str(corpus_id)

    async def test_corpus_delete_audit_actor_is_api_key(self, client, tmp_path):
        """Audit record actor is 'api_key' (not 'system') for API-key auth (R-003)."""
        (tmp_path / "g.txt").write_text("data\n")
        create_r = await client.post(
            "/v1/corpora",
            json={"name": "stride-audit-corpus-2", "root_path": str(tmp_path)},
        )
        assert create_r.status_code == 200
        corpus_id = create_r.json()["data"]["id"]

        await client.delete(f"/v1/corpora/{corpus_id}")

        from anvil.db.repositories.audit_events import AuditEventRepository
        from anvil.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            repo = AuditEventRepository(session)
            events = await repo.query(
                action_type=AuditAction.DELETE.value,
                target_type=AuditTargetType.CORPUS.value,
                limit=10,
            )
        assert events
        assert (
            events[-1].actor == "api_key"
        ), f"Expected actor='api_key', got {events[-1].actor!r}"


####################################################################
# R-002: model archive — audit record emitted
####################################################################


class TestModelArchiveAudit:
    """DELETE /v1/models/{name}/versions/{version} must emit an audit record (R-002)."""

    @pytest.fixture
    def mock_workbench(self):
        """Minimal workbench mock for model archive tests."""
        wb = _make_workbench_with_audit()
        wb.catalog = MagicMock()
        wb.catalog.get_entry = AsyncMock()
        wb.catalog.archive = AsyncMock()
        return wb

    @pytest.fixture
    def override_dep(self, mock_workbench):
        """Override get_workbench with mock_workbench."""
        app.dependency_overrides[get_workbench] = lambda: mock_workbench
        yield
        app.dependency_overrides.clear()

    async def test_model_archive_emits_audit_record(
        self, client, mock_workbench, override_dep
    ):
        """Audit record with action_type=delete, target_type=model is created."""
        entry = MagicMock()
        mock_workbench.catalog.get_entry.return_value = entry

        resp = await client.delete("/v1/models/my-model/versions/1")
        assert resp.status_code == 200

        mock_workbench.audit.record.assert_awaited_once()
        call_kwargs = mock_workbench.audit.record.call_args.kwargs
        assert call_kwargs["action_type"] == AuditAction.DELETE.value
        assert call_kwargs["target_type"] == AuditTargetType.MODEL.value

    async def test_model_archive_audit_actor_is_api_key(
        self, client, mock_workbench, override_dep
    ):
        """Audit record actor is 'api_key' (not 'system') for API-key auth (R-003)."""
        entry = MagicMock()
        mock_workbench.catalog.get_entry.return_value = entry

        await client.delete("/v1/models/my-model/versions/1")

        call_kwargs = mock_workbench.audit.record.call_args.kwargs
        assert (
            call_kwargs["actor"] == "api_key"
        ), f"Expected actor='api_key', got {call_kwargs['actor']!r}"

    async def test_model_archive_not_found_no_audit(
        self, client, mock_workbench, override_dep
    ):
        """No audit record when model is not found (404)."""
        mock_workbench.catalog.get_entry.return_value = None

        resp = await client.delete("/v1/models/missing/versions/1")
        assert resp.status_code == 404
        mock_workbench.audit.record.assert_not_awaited()


####################################################################
# R-002: experiment delete — audit record emitted
####################################################################


class TestExperimentDeleteAudit:
    """DELETE /v1/experiments/{id} must emit an audit record (R-002)."""

    @pytest.fixture
    def mock_workbench(self):
        """Minimal workbench mock for experiment delete tests."""
        return _make_workbench_with_audit()

    @pytest.fixture
    def override_dep(self, mock_workbench):
        """Override get_workbench with mock_workbench."""
        app.dependency_overrides[get_workbench] = lambda: mock_workbench
        yield
        app.dependency_overrides.clear()

    async def test_experiment_delete_emits_audit_record(
        self, client, mock_workbench, override_dep
    ):
        """Audit record with action_type=experiment_delete is created."""
        with patch.object(
            TrackingService,
            "get_experiment",
            return_value={"id": 1, "mlflow_run_id": None},
        ):
            resp = await client.delete("/v1/experiments/1")
        assert resp.status_code == 200

        mock_workbench.audit.record.assert_awaited_once()
        call_kwargs = mock_workbench.audit.record.call_args.kwargs
        assert call_kwargs["action_type"] == AuditAction.EXPERIMENT_DELETE.value
        assert call_kwargs["target_type"] == AuditTargetType.EXPERIMENT.value
        assert call_kwargs["target_id"] == "1"

    async def test_experiment_delete_audit_actor_is_api_key(
        self, client, mock_workbench, override_dep
    ):
        """Audit record actor is 'api_key' (not 'system') for API-key auth (R-003)."""
        with patch.object(
            TrackingService,
            "get_experiment",
            return_value={"id": 1, "mlflow_run_id": None},
        ):
            await client.delete("/v1/experiments/1")

        call_kwargs = mock_workbench.audit.record.call_args.kwargs
        assert (
            call_kwargs["actor"] == "api_key"
        ), f"Expected actor='api_key', got {call_kwargs['actor']!r}"

    async def test_experiment_delete_not_found_no_audit(
        self, client, mock_workbench, override_dep
    ):
        """No audit record when experiment is not found (404)."""
        with patch.object(TrackingService, "get_experiment", return_value=None):
            resp = await client.delete("/v1/experiments/999")
        assert resp.status_code == 404
        mock_workbench.audit.record.assert_not_awaited()


####################################################################
# R-003: existing call sites — dataset upload actor
####################################################################


class TestDatasetUploadAuditActor:
    """POST /v1/datasets/upload audit actor must not be 'system' (R-003)."""

    @pytest.fixture
    def mock_workbench(self):
        """Minimal workbench mock for dataset upload tests."""
        wb = _make_workbench_with_audit()
        wb.tracking = MagicMock()
        wb.tracking.is_degraded = True

        ds = MagicMock()
        ds.id = 1
        ds.name = "test.txt"
        ds.description = None
        ds.filename = "test.txt"
        ds.sample_count = 2
        ds.total_size_bytes = 20
        ds.status = "ready"
        ds.curation_version = 0
        ds.vocabulary_size = 7
        ds.document_count = 2
        ds.created_at = "2026-01-01"
        ds.updated_at = "2026-01-01"

        wb.datasets = MagicMock()
        wb.datasets.create_dataset = AsyncMock(return_value=ds)
        wb.session.refresh = AsyncMock()
        return wb

    @pytest.fixture
    def override_dep(self, mock_workbench):
        app.dependency_overrides[get_workbench] = lambda: mock_workbench
        yield
        app.dependency_overrides.clear()

    async def test_upload_audit_actor_is_api_key(
        self, client, mock_workbench, override_dep
    ):
        """Audit record actor is 'api_key' (not 'system') for API-key auth."""
        resp = await client.post(
            "/v1/datasets/upload",
            files={"file": ("test.txt", b"hello\nworld\n", "text/plain")},
        )
        assert resp.status_code == 200

        mock_workbench.audit.record.assert_awaited_once()
        call_kwargs = mock_workbench.audit.record.call_args.kwargs
        assert (
            call_kwargs["actor"] == "api_key"
        ), f"Expected actor='api_key', got {call_kwargs['actor']!r}"


####################################################################
# R-003: existing call sites — dataset import actor
####################################################################


class TestDatasetImportAuditActor:
    """POST /v1/datasets/{id}/import audit actor must not be 'system' (R-003)."""

    @pytest.fixture
    def mock_workbench(self):
        """Minimal workbench mock for dataset import tests."""
        wb = _make_workbench_with_audit()
        wb.tracking = MagicMock()
        wb.tracking.is_degraded = True

        import_result = MagicMock()
        import_result.rows_imported = 2
        import_result.import_source_id = 1
        import_result.errors = []
        import_result.preview = ["hello", "world"]

        import_svc = MagicMock()
        import_svc.commit_import = AsyncMock(return_value=import_result)
        wb.dataset_import = MagicMock(return_value=import_svc)
        return wb

    @pytest.fixture
    def override_dep(self, mock_workbench):
        app.dependency_overrides[get_workbench] = lambda: mock_workbench
        yield
        app.dependency_overrides.clear()

    async def test_import_audit_actor_is_api_key(
        self, client, mock_workbench, override_dep
    ):
        """Audit record actor is 'api_key' (not 'system') for API-key auth."""
        resp = await client.post(
            "/v1/datasets/1/import",
            json={"format": "txt", "text": "hello\nworld\n"},
        )
        assert resp.status_code == 200

        mock_workbench.audit.record.assert_awaited_once()
        call_kwargs = mock_workbench.audit.record.call_args.kwargs
        assert (
            call_kwargs["actor"] == "api_key"
        ), f"Expected actor='api_key', got {call_kwargs['actor']!r}"


####################################################################
# get_actor_from_request unit tests
####################################################################


class TestGetActorFromRequest:
    """Unit tests for the ``get_actor_from_request`` helper."""

    def test_returns_api_key_when_header_present(self):
        """Returns 'api_key' when X-API-Key header is set."""
        from unittest.mock import MagicMock

        from anvil.api.deps import get_actor_from_request

        req = MagicMock()
        req.headers = {"X-API-Key": "some-key"}
        req.cookies = {}
        assert get_actor_from_request(req) == "api_key"

    def test_returns_session_fingerprint_when_cookie_present(self):
        """Returns 'session:<8chars>' when session cookie is set."""
        from anvil.api.deps import get_actor_from_request

        req = MagicMock()
        req.headers = {}
        req.cookies = {"anvil_session": "abcdefghijklmnop"}
        actor = get_actor_from_request(req)
        assert actor == "session:abcdefgh"

    def test_returns_anonymous_when_no_credentials(self):
        """Returns 'anonymous' when neither header nor cookie is present."""
        from anvil.api.deps import get_actor_from_request

        req = MagicMock()
        req.headers = {}
        req.cookies = {}
        assert get_actor_from_request(req) == "anonymous"

    def test_api_key_takes_precedence_over_cookie(self):
        """API key takes precedence when both header and cookie are present."""
        from anvil.api.deps import get_actor_from_request

        req = MagicMock()
        req.headers = {"X-API-Key": "some-key"}
        req.cookies = {"anvil_session": "abcdefghijklmnop"}
        assert get_actor_from_request(req) == "api_key"
