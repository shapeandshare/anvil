# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for TrackingService with injected fake client factory."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mlflow.entities import Run

from anvil.config import get_config


@dataclass
class FakeRun:
    info: Run | None = None


@dataclass
class FakeExperiment:
    experiment_id: str = "exp_1"


class FakeMlflowClient:
    def __init__(self, tracking_uri: str):
        self.tracking_uri = tracking_uri
        self.created_runs: list[dict] = []
        self.logged_metrics: list[dict] = []
        self.set_terminated_calls: list[dict] = []
        self.log_artifact_calls: list[dict] = []
        self.logged_params: list[dict] = []
        self.searched_runs: list = []
        self.create_run_fail: bool = False

    def get_experiment_by_name(self, name: str) -> FakeExperiment | None:
        return FakeExperiment(experiment_id="exp_1")

    def create_experiment(self, name: str) -> str:
        return "exp_1"

    def create_run(
        self, experiment_id: str, run_name: str | None = None, tags: dict | None = None
    ):
        if self.create_run_fail:
            raise ConnectionError("MLflow server unreachable")
        run_id = f"run_{len(self.created_runs) + 1}"
        self.created_runs.append(
            {
                "experiment_id": experiment_id,
                "run_name": run_name,
                "run_id": run_id,
                "tags": tags,
            }
        )
        return FakeRun(info=MagicMock(run_id=run_id))

    def log_batch(
        self,
        run_id: str,
        params: list | None = None,
        metrics: list | None = None,
        tags: list | None = None,
    ):
        self.logged_params.append({"run_id": run_id, "params": params or []})

    def log_metric(self, run_id: str, key: str, value: float, step: int | None = None):
        self.logged_metrics.append(
            {"run_id": run_id, "key": key, "value": value, "step": step}
        )

    def set_terminated(self, run_id: str, status: str = "FINISHED"):
        self.set_terminated_calls.append({"run_id": run_id, "status": status})

    def log_input(self, run_id: str, dataset: object, context: str | None = None):
        if not hasattr(self, "logged_inputs"):
            self.logged_inputs: list[dict] = []
        self.logged_inputs.append(
            {"run_id": run_id, "dataset": dataset, "context": context}
        )

    def log_artifact(self, run_id: str, local_path: str):
        self.log_artifact_calls.append({"run_id": run_id, "local_path": local_path})

    def search_runs(self, experiment_ids: list[str], filter_string: str):
        return self.searched_runs


def fake_client_factory(tracking_uri: str) -> FakeMlflowClient:
    return FakeMlflowClient(tracking_uri)


@pytest.fixture
def svc():
    from anvil.services.tracking.tracking import TrackingService

    return TrackingService(
        tracking_uri="http://127.0.0.1:5000", client_factory=fake_client_factory
    )


@pytest.mark.asyncio
async def test_start_run_returns_run_id(svc):
    run_id = await svc.start_run(
        run_name="test-run",
        params={"n_layer": 1},
        engine_backend="stdlib",
        device="cpu",
    )
    assert isinstance(run_id, str)
    assert len(run_id) > 0


@pytest.mark.asyncio
async def test_start_run_logs_params(svc):
    await svc.start_run(
        run_name="param-test",
        params={"n_layer": 2, "n_embd": 32},
        engine_backend="torch",
        device="mps",
    )
    client = svc._client
    assert len(client.logged_params) >= 1


@pytest.mark.asyncio
async def test_log_metric(svc):
    run_id = await svc.start_run(
        run_name="metric-test", params={}, engine_backend="stdlib", device="cpu"
    )
    await svc.log_metric(run_id, "loss", 0.5, step=1)
    client = svc._client
    assert any(
        m["key"] == "loss" and m["value"] == 0.5 and m["step"] == 1
        for m in client.logged_metrics
    )


@pytest.mark.asyncio
async def test_log_final_metric(svc):
    run_id = await svc.start_run(
        run_name="final-metric", params={}, engine_backend="stdlib", device="cpu"
    )
    await svc.log_final_metric(run_id, "final_loss", 0.3)
    client = svc._client
    assert any(
        m["key"] == "final_loss" and m["value"] == 0.3 for m in client.logged_metrics
    )


@pytest.mark.asyncio
async def test_finish_run(svc):
    run_id = await svc.start_run(
        run_name="finish", params={}, engine_backend="stdlib", device="cpu"
    )
    await svc.finish_run(run_id)
    client = svc._client
    assert any(
        c["run_id"] == run_id and c["status"] == "FINISHED"
        for c in client.set_terminated_calls
    )


@pytest.mark.asyncio
async def test_fail_run(svc):
    run_id = await svc.start_run(
        run_name="fail", params={}, engine_backend="stdlib", device="cpu"
    )
    await svc.fail_run(run_id, reason="oops")
    client = svc._client
    assert any(
        c["run_id"] == run_id and c["status"] == "FAILED"
        for c in client.set_terminated_calls
    )


@pytest.mark.asyncio
async def test_log_artifacts(svc):
    run_id = await svc.start_run(
        run_name="artifacts", params={}, engine_backend="stdlib", device="cpu"
    )
    await svc.log_artifacts(
        run_id, model_path="/fake/model.json", samples="test", vocab=None
    )
    client = svc._client
    assert len(client.log_artifact_calls) > 0


@pytest.mark.asyncio
async def test_degraded_mode_on_connection_error():
    from anvil.services.tracking.tracking import TrackingService

    def failing_factory(tracking_uri: str):
        client = FakeMlflowClient(tracking_uri)
        client.create_run_fail = True
        return client

    svc = TrackingService(
        tracking_uri="http://unreachable:5000", client_factory=failing_factory
    )
    run_id = await svc.start_run(
        run_name="degraded", params={}, engine_backend="stdlib", device="cpu"
    )
    assert run_id == ""
    assert svc.is_degraded is True


@pytest.mark.asyncio
async def test_degraded_noop_on_subsequent_calls(svc):
    from anvil.services.tracking.tracking import TrackingService

    class DegradedClient(FakeMlflowClient):
        def create_run(self, experiment_id, run_name=None, tags=None):
            raise ConnectionError("fail")

    svc2 = TrackingService(
        tracking_uri="http://fail:5000",
        client_factory=lambda uri: DegradedClient(uri),
    )
    run_id = await svc2.start_run(
        run_name="d", params={}, engine_backend="stdlib", device="cpu"
    )
    assert svc2.is_degraded
    await svc2.log_metric(run_id, "loss", 0.5, step=1)
    await svc2.finish_run(run_id)
    assert len(svc2._client.set_terminated_calls) == 0


@pytest.mark.asyncio
async def test_capabilities(svc):
    caps = await svc.capabilities()
    assert caps.mlflow_version.startswith("3.")
    assert isinstance(caps.server_backed, bool)
    assert isinstance(caps.genai_datasets, bool)


@pytest.mark.asyncio
async def test_construct_with_default_uri():
    from anvil.services.tracking.tracking import TrackingService

    svc = TrackingService(client_factory=fake_client_factory)
    cfg = get_config()
    assert svc._tracking_uri == cfg["mlflow_uri"]


@pytest.mark.asyncio
async def test_reconcile_orphans(svc):
    await svc.start_run(
        run_name="reconcile", params={}, engine_backend="stdlib", device="cpu"
    )
    client = svc._client
    client.searched_runs = []
    result = await svc.reconcile_orphans()
    assert isinstance(result, list)


class TestLogDatasetInput:
    @pytest.mark.asyncio
    async def test_calls_log_input_and_returns_digest(self, svc):
        run_id = await svc.start_run(
            run_name="lineage-ds", params={}, engine_backend="stdlib", device="cpu"
        )

        mock_session = AsyncMock()
        with patch(
            "anvil.services.tracking.mlflow_inputs.MlflowInputResolver"
        ) as resolver_cls:
            mock_resolver = AsyncMock()
            resolver_cls.return_value = mock_resolver
            mock_resolver.resolve_dataset.return_value = (
                "fake_dataset",
                "abc123digest",
            )

            digest = await svc.log_dataset_input(
                run_id, dataset_id=1, role="training", session=mock_session
            )

            assert digest == "abc123digest"
            client = svc._client
            assert any(
                inp["run_id"] == run_id and inp["context"] == "training"
                for inp in client.logged_inputs
            )

    @pytest.mark.asyncio
    async def test_degraded_returns_empty_string(self, svc):
        svc._degraded = True
        digest = await svc.log_dataset_input("run_1", dataset_id=1)
        assert digest == ""

    @pytest.mark.asyncio
    async def test_no_run_id_returns_empty_string(self, svc):
        digest = await svc.log_dataset_input("", dataset_id=1)
        assert digest == ""

    @pytest.mark.asyncio
    async def test_resolver_failure_returns_empty_string(self, svc):
        run_id = await svc.start_run(
            run_name="fail-resolver", params={}, engine_backend="stdlib", device="cpu"
        )

        with patch(
            "anvil.services.tracking.mlflow_inputs.MlflowInputResolver"
        ) as resolver_cls:
            mock_session = AsyncMock()
            mock_resolver = AsyncMock()
            resolver_cls.return_value = mock_resolver
            mock_resolver.resolve_dataset.side_effect = ValueError("boom")

            digest = await svc.log_dataset_input(
                run_id, dataset_id=1, session=mock_session
            )
            assert digest == ""


class TestLogCorpusInput:
    @pytest.mark.asyncio
    async def test_calls_log_input_and_log_artifacts(self, svc):
        run_id = await svc.start_run(
            run_name="lineage-corpus", params={}, engine_backend="stdlib", device="cpu"
        )

        mock_session = AsyncMock()
        with patch(
            "anvil.services.tracking.mlflow_inputs.MlflowInputResolver"
        ) as resolver_cls:
            mock_resolver = AsyncMock()
            resolver_cls.return_value = mock_resolver
            mock_resolver.resolve_corpus.return_value = (
                "fake_meta_ds",
                ["/tmp/a.py", "/tmp/b.py"],
                "corpus_digest",
            )

            digest = await svc.log_corpus_input(
                run_id, corpus_id=1, session=mock_session
            )

            assert digest == "corpus_digest"
            client = svc._client
            assert any(
                inp["run_id"] == run_id and inp["context"] == "corpus"
                for inp in client.logged_inputs
            )
            assert len(client.log_artifact_calls) >= 2

    @pytest.mark.asyncio
    async def test_degraded_returns_empty_string(self, svc):
        svc._degraded = True
        digest = await svc.log_corpus_input("run_1", corpus_id=1)
        assert digest == ""

    @pytest.mark.asyncio
    async def test_no_run_id_returns_empty_string(self, svc):
        digest = await svc.log_corpus_input("", corpus_id=1)
        assert digest == ""

    @pytest.mark.asyncio
    async def test_resolver_failure_returns_empty_string(self, svc):
        run_id = await svc.start_run(
            run_name="fail-corpus", params={}, engine_backend="stdlib", device="cpu"
        )

        with patch(
            "anvil.services.tracking.mlflow_inputs.MlflowInputResolver"
        ) as resolver_cls:
            mock_session = AsyncMock()
            mock_resolver = AsyncMock()
            resolver_cls.return_value = mock_resolver
            mock_resolver.resolve_corpus.side_effect = ValueError("boom")

            digest = await svc.log_corpus_input(
                run_id, corpus_id=1, session=mock_session
            )
            assert digest == ""


class TestLogDatasetLifecycleEvent:
    """Tests for TrackingService.log_dataset_lifecycle_event()."""

    @pytest.mark.asyncio
    async def test_creates_run_with_correct_tags(self):
        """Should create a short-lived MLflow run."""
        from anvil.services.tracking.tracking import TrackingService

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000", client_factory=fake_client_factory
        )
        run_id = await svc.log_dataset_lifecycle_event(
            dataset_id=42,
            event_type="create",
            params={"name": "test-ds", "sample_count": 100},
        )
        assert run_id, "Expected non-empty run_id"
        client = svc._client
        assert client is not None

    @pytest.mark.asyncio
    async def test_degraded_mode_returns_empty(self):
        """Should return '' when service is degraded."""
        from anvil.services.tracking.tracking import TrackingService

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000", client_factory=fake_client_factory
        )
        svc._degraded = True
        run_id = await svc.log_dataset_lifecycle_event(
            dataset_id=42, event_type="create"
        )
        assert run_id == ""

    @pytest.mark.asyncio
    async def test_empty_run_id_on_connection_error(self):
        """Should return '' and set degraded on connection error."""
        from anvil.services.tracking.tracking import TrackingService

        def broken_factory(uri):
            raise ConnectionError("Connection refused")

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000", client_factory=broken_factory
        )
        run_id = await svc.log_dataset_lifecycle_event(
            dataset_id=42, event_type="create"
        )
        assert run_id == ""
        assert svc.is_degraded

    @pytest.mark.asyncio
    async def test_multiple_event_types(self):
        """Should handle all event types: create, import, curate, update, delete."""
        from anvil.services.tracking.tracking import TrackingService

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000", client_factory=fake_client_factory
        )
        for event_type in ("create", "import", "curate", "update", "delete"):
            run_id = await svc.log_dataset_lifecycle_event(
                dataset_id=1, event_type=event_type
            )
            assert run_id, f"Expected non-empty run_id for event_type={event_type}"


class TestLogCorpusLifecycleEvent:
    """Tests for TrackingService.log_corpus_lifecycle_event()."""

    @pytest.mark.asyncio
    async def test_creates_run_with_correct_tags(self):
        """Should create a short-lived MLflow run for corpus events."""
        from anvil.services.tracking.tracking import TrackingService

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000", client_factory=fake_client_factory
        )
        run_id = await svc.log_corpus_lifecycle_event(
            corpus_id=7,
            event_type="ingest",
            params={"file_count": 15, "document_count": 200},
            tags={"anvil.parent_corpus_id": "3"},
        )
        assert run_id, "Expected non-empty run_id"
        client = svc._client
        assert client is not None

    @pytest.mark.asyncio
    async def test_degraded_mode_returns_empty(self):
        """Should return '' when service is degraded."""
        from anvil.services.tracking.tracking import TrackingService

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000", client_factory=fake_client_factory
        )
        svc._degraded = True
        run_id = await svc.log_corpus_lifecycle_event(corpus_id=7, event_type="ingest")
        assert run_id == ""

    @pytest.mark.asyncio
    async def test_empty_run_id_on_connection_error(self):
        """Should return '' and set degraded on connection error."""
        from anvil.services.tracking.tracking import TrackingService

        def broken_factory(uri):
            raise ConnectionError("Connection refused")

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000", client_factory=broken_factory
        )
        run_id = await svc.log_corpus_lifecycle_event(corpus_id=7, event_type="ingest")
        assert run_id == ""
        assert svc.is_degraded
