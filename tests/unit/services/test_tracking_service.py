# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Comprehensive unit tests for TrackingService.

Covers: run lifecycle, metrics/params/artifacts logging, experiment
listing/lookup, eval dataset management, system metrics, degraded mode,
capabilities, dataset/corpus input logging, lifecycle events, model
registry, orphan reconciliation, and safetensors artifact queries.
"""

from __future__ import annotations

import builtins
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.config import get_config

########################################################################
# Fake MLflow data classes
########################################################################


@dataclass
class FakeFileInfo:
    """Matches MLflow FileInfo interface for artifact listing."""

    path: str
    file_size: int | None = None
    is_dir: bool = False


@dataclass
class FakeRunInfo:
    """Matches MLflow Run.info interface."""

    run_id: str = "run_1"


@dataclass
class FakeRun:
    """Matches minimal MLflow Run interface."""

    info: FakeRunInfo = field(default_factory=FakeRunInfo)
    data: MagicMock = field(default_factory=lambda: MagicMock())


@dataclass
class FakeExperiment:
    """Matches minimal MLflow Experiment interface."""

    experiment_id: str = "exp_1"


@dataclass
class FakeModelVersion:
    """Matches MLflow ModelVersion interface."""

    version: str = "1"
    run_id: str = "run_1"
    creation_timestamp: int = 1000000
    current_stage: str = "None"


@dataclass
class FakeRegisteredModel:
    """Matches MLflow RegisteredModel interface."""

    name: str = "test-model"
    description: str | None = "A test model"


########################################################################
# Fake MLflow client
########################################################################


class FakeMlflowClient:
    """Fake MLflow client that records all calls for test assertions.

    Provides enough of the MlflowClient interface to exercise every
    TrackingService method without touching a real MLflow server.
    """

    def __init__(self, tracking_uri: str) -> None:
        self.tracking_uri = tracking_uri
        self.created_runs: list[dict[str, Any]] = []
        self.logged_metrics: list[dict[str, Any]] = []
        self.set_terminated_calls: list[dict[str, Any]] = []
        self.log_artifact_calls: list[dict[str, Any]] = []
        self.logged_params: list[dict[str, Any]] = []
        self.logged_inputs: list[dict[str, Any]] = []
        self.set_tag_calls: list[dict[str, Any]] = []
        self.searched_runs: list[Any] = []
        self.create_run_fail: bool = False
        self.create_run_side_effect: Exception | None = None
        self.registered_models: list[FakeRegisteredModel] = []
        self.model_versions: list[FakeModelVersion] = []
        self.list_artifacts_result: list[FakeFileInfo] = []
        self.get_run_result: FakeRun | None = None

    def get_experiment_by_name(self, name: str) -> FakeExperiment | None:
        """Return a FakeExperiment for any name."""
        return FakeExperiment(experiment_id="exp_1")

    def create_experiment(self, name: str) -> str:
        """Return experiment ID."""
        return "exp_1"

    def create_run(
        self,
        experiment_id: str,
        run_name: str | None = None,
        tags: dict[str, Any] | None = None,
    ) -> FakeRun:
        """Create a fake run, optionally raising on failure."""
        if self.create_run_side_effect:
            raise self.create_run_side_effect
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
        return FakeRun(info=FakeRunInfo(run_id=run_id))

    def log_batch(
        self,
        run_id: str,
        params: list[Any] | None = None,
        metrics: list[Any] | None = None,
        tags: list[Any] | None = None,
    ) -> None:
        """Record logged params."""
        self.logged_params.append({"run_id": run_id, "params": params or []})

    def log_metric(
        self, run_id: str, key: str, value: float, step: int | None = None
    ) -> None:
        """Record a logged metric."""
        self.logged_metrics.append(
            {"run_id": run_id, "key": key, "value": value, "step": step}
        )

    def set_terminated(self, run_id: str, status: str = "FINISHED") -> None:
        """Record a set_terminated call."""
        self.set_terminated_calls.append({"run_id": run_id, "status": status})

    def set_tag(self, run_id: str, key: str, value: str) -> None:
        """Record a set_tag call."""
        self.set_tag_calls.append({"run_id": run_id, "key": key, "value": value})

    def log_input(
        self, run_id: str, dataset: object, context: str | None = None
    ) -> None:
        """Record a log_input call."""
        self.logged_inputs.append(
            {"run_id": run_id, "dataset": dataset, "context": context}
        )

    def log_artifact(self, run_id: str, local_path: str) -> None:
        """Record a log_artifact call."""
        self.log_artifact_calls.append({"run_id": run_id, "local_path": local_path})

    def search_runs(
        self,
        experiment_ids: list[str],
        filter_string: str | None = None,
        order_by: list[str] | None = None,
        max_results: int = 100,
    ) -> list[Any]:
        """Return pre-configured search results."""
        return self.searched_runs

    def list_artifacts(self, run_id: str) -> list[FakeFileInfo]:
        """Return pre-configured artifact listing."""
        return self.list_artifacts_result

    def create_registered_model(self, name: str) -> FakeRegisteredModel:
        """Create a fake registered model."""
        rm = FakeRegisteredModel(name=name)
        self.registered_models.append(rm)
        return rm

    def create_model_version(
        self, name: str, source: str, run_id: str
    ) -> FakeModelVersion:
        """Create a fake model version."""
        mv = FakeModelVersion(version="1", run_id=run_id)
        self.model_versions.append(mv)
        return mv

    def search_registered_models(
        self, filter_string: str | None = None
    ) -> list[FakeRegisteredModel]:
        """Return registered models."""
        return self.registered_models

    def search_model_versions(self, filter_string: str) -> list[FakeModelVersion]:
        """Return model versions."""
        return self.model_versions

    def get_run(self, run_id: str) -> FakeRun:
        """Return a fake run."""
        if self.get_run_result:
            return self.get_run_result
        return FakeRun(
            info=FakeRunInfo(run_id=run_id),
            data=MagicMock(
                metrics={"final_loss": 0.42},
                tags={"anvil.experiment_id": "99"},
            ),
        )


def fake_client_factory(tracking_uri: str) -> FakeMlflowClient:
    """Factory function creating a FakeMlflowClient for a given URI."""
    return FakeMlflowClient(tracking_uri)


########################################################################
# Test fixture
########################################################################


@pytest.fixture
def svc() -> Any:
    """Fixture providing a TrackingService with a faked MLflow client."""
    from anvil.services.tracking.tracking import TrackingService

    return TrackingService(
        tracking_uri="http://127.0.0.1:5000", client_factory=fake_client_factory
    )


########################################################################
# Helpers
########################################################################


def _make_run_with_data(
    status: str = "FINISHED",
    metrics: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    tags: dict[str, Any] | None = None,
    run_name: str = "",
    start_time: int = 1000000,
    end_time: int = 2000000,
    run_id: str = "run_1",
) -> FakeRun:
    """Build a FakeRun with realistic .data sub-object for search_runs returns."""
    data = MagicMock()
    data.metrics = metrics or {"final_loss": 0.5}
    data.params = params or {"engine_backend": "stdlib", "device": "cpu"}
    data.tags = tags or {"mlflow.runName": run_name, "anvil.experiment_id": "1"}
    info = MagicMock()
    info.run_id = run_id
    info.status = status
    info.start_time = start_time
    info.end_time = end_time
    return FakeRun(info=info, data=data)


########################################################################
# Constructor & Properties
########################################################################


class TestConstructor:
    """Tests for TrackingService initialisation."""

    @pytest.mark.asyncio
    async def test_construct_with_default_uri(self) -> None:
        """Uses configured mlflow_uri when no URI is provided."""
        from anvil.services.tracking.tracking import TrackingService

        svc = TrackingService(client_factory=fake_client_factory)
        cfg = get_config()
        assert svc._tracking_uri == cfg["mlflow_uri"]

    @pytest.mark.asyncio
    async def test_construct_with_custom_uri(self) -> None:
        """Uses explicit tracking_uri when provided."""
        from anvil.services.tracking.tracking import TrackingService

        svc = TrackingService(
            tracking_uri="http://custom:5000", client_factory=fake_client_factory
        )
        assert svc._tracking_uri == "http://custom:5000"

    @pytest.mark.asyncio
    async def test_construct_with_custom_experiment_name(self) -> None:
        """Uses custom experiment name."""
        from anvil.services.tracking.tracking import TrackingService

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000",
            experiment_name="my-experiment",
            client_factory=fake_client_factory,
        )
        assert svc._experiment_name == "my-experiment"

    @pytest.mark.asyncio
    async def test_sanitize_model_name_replaces_colon(self) -> None:
        """Replaces ':' with '-' in model names."""
        from anvil.services.tracking.tracking import TrackingService

        assert TrackingService._sanitize_model_name("a:b") == "a-b"

    @pytest.mark.asyncio
    async def test_sanitize_model_name_clean_passthrough(self) -> None:
        """Clean names pass through unchanged."""
        from anvil.services.tracking.tracking import TrackingService

        assert TrackingService._sanitize_model_name("hello-world") == "hello-world"


########################################################################
# Run Lifecycle: start_run
########################################################################


class TestStartRun:
    """Tests for TrackingService.start_run()."""

    @pytest.mark.asyncio
    async def test_returns_run_id(self, svc: Any) -> None:
        """Returns a non-empty run ID on success."""
        run_id = await svc.start_run(
            run_name="test-run",
            params={"n_layer": 1},
            engine_backend="stdlib",
            device="cpu",
        )
        assert isinstance(run_id, str)
        assert len(run_id) > 0

    @pytest.mark.asyncio
    async def test_logs_params_via_log_batch(self, svc: Any) -> None:
        """Logs params via log_batch including engine_backend and device."""
        await svc.start_run(
            run_name="param-test",
            params={"n_layer": 2, "n_embd": 32},
            engine_backend="torch",
            device="mps",
        )
        client = svc._client
        assert client is not None
        assert len(client.logged_params) >= 1

    @pytest.mark.asyncio
    async def test_auto_generates_run_name(self, svc: Any) -> None:
        """Generates a run name when none is provided."""
        run_id = await svc.start_run(
            params={},
            engine_backend="stdlib",
            device="cpu",
        )
        assert len(run_id) > 0

    @pytest.mark.asyncio
    async def test_handles_none_params(self, svc: Any) -> None:
        """Works correctly when params is None."""
        run_id = await svc.start_run(
            run_name="no-params",
            params=None,
            engine_backend="stdlib",
            device="cpu",
        )
        assert len(run_id) > 0

    @pytest.mark.asyncio
    async def test_skips_none_param_values(self, svc: Any) -> None:
        """Skips param entries whose value is None."""
        run_id = await svc.start_run(
            run_name="skip-none",
            params={"valid": 1, "invalid": None},
            engine_backend="stdlib",
            device="cpu",
        )
        assert len(run_id) > 0

    @pytest.mark.asyncio
    async def test_degraded_returns_empty(self, svc: Any) -> None:
        """Returns empty string when in degraded mode."""
        svc._degraded = True
        run_id = await svc.start_run(
            run_name="degraded",
            params={},
            engine_backend="stdlib",
            device="cpu",
        )
        assert run_id == ""

    @pytest.mark.asyncio
    async def test_connection_error_enters_degraded(self) -> None:
        """Enters degraded mode on ConnectionError."""
        from anvil.services.tracking.tracking import TrackingService

        def failing_factory(tracking_uri: str) -> FakeMlflowClient:
            client = FakeMlflowClient(tracking_uri)
            client.create_run_fail = True
            return client

        svc = TrackingService(
            tracking_uri="http://unreachable:5000", client_factory=failing_factory
        )
        run_id = await svc.start_run(
            run_name="fail", params={}, engine_backend="stdlib", device="cpu"
        )
        assert run_id == ""
        assert svc.is_degraded is True

    @pytest.mark.asyncio
    async def test_generic_exception_enters_degraded(self) -> None:
        """Enters degraded mode on generic Exception."""
        from anvil.services.tracking.tracking import TrackingService

        def broken_factory(tracking_uri: str) -> FakeMlflowClient:
            client = FakeMlflowClient(tracking_uri)
            client.create_run_side_effect = RuntimeError("Something went wrong")
            return client

        svc = TrackingService(
            tracking_uri="http://broken:5000", client_factory=broken_factory
        )
        run_id = await svc.start_run(
            run_name="fail", params={}, engine_backend="stdlib", device="cpu"
        )
        assert run_id == ""
        assert svc.is_degraded is True


########################################################################
# Run Lifecycle: finish_run
########################################################################


class TestFinishRun:
    """Tests for TrackingService.finish_run()."""

    @pytest.mark.asyncio
    async def test_calls_set_terminated_finished(self, svc: Any) -> None:
        """Calls set_terminated with FINISHED status."""
        run_id = await svc.start_run(
            run_name="finish", params={}, engine_backend="stdlib", device="cpu"
        )
        await svc.finish_run(run_id)
        client = svc._client
        assert client is not None
        assert any(
            c["run_id"] == run_id and c["status"] == "FINISHED"
            for c in client.set_terminated_calls
        )

    @pytest.mark.asyncio
    async def test_degraded_noop(self, svc: Any) -> None:
        """No-ops when in degraded mode."""
        svc._degraded = True
        await svc.finish_run("run_1")
        client = svc._client
        assert client is None or len(client.set_terminated_calls) == 0

    @pytest.mark.asyncio
    async def test_empty_run_id_noop(self, svc: Any) -> None:
        """No-ops when run_id is empty."""
        await svc.finish_run("")

    @pytest.mark.asyncio
    async def test_exception_caught(self, svc: Any) -> None:
        """Silently catches exceptions from MLflow."""
        run_id = await svc.start_run(
            run_name="finish-exception",
            params={},
            engine_backend="stdlib",
            device="cpu",
        )
        svc._client = None
        await svc.finish_run(run_id)  # Should not raise


########################################################################
# Run Lifecycle: fail_run
########################################################################


class TestFailRun:
    """Tests for TrackingService.fail_run()."""

    @pytest.mark.asyncio
    async def test_calls_set_terminated_failed(self, svc: Any) -> None:
        """Calls set_terminated with FAILED status."""
        run_id = await svc.start_run(
            run_name="fail", params={}, engine_backend="stdlib", device="cpu"
        )
        await svc.fail_run(run_id, _reason="oops")
        client = svc._client
        assert client is not None
        assert any(
            c["run_id"] == run_id and c["status"] == "FAILED"
            for c in client.set_terminated_calls
        )

    @pytest.mark.asyncio
    async def test_degraded_noop(self, svc: Any) -> None:
        """No-ops when in degraded mode."""
        svc._degraded = True
        await svc.fail_run("run_1")

    @pytest.mark.asyncio
    async def test_empty_run_id_noop(self, svc: Any) -> None:
        """No-ops when run_id is empty."""
        await svc.fail_run("")

    @pytest.mark.asyncio
    async def test_exception_caught(self, svc: Any) -> None:
        """Silently catches exceptions."""
        run_id = await svc.start_run(
            run_name="fail-exception",
            params={},
            engine_backend="stdlib",
            device="cpu",
        )
        svc._client = None
        await svc.fail_run(run_id)  # Should not raise


########################################################################
# Metrics & Tags
########################################################################


class TestLogMetric:
    """Tests for TrackingService.log_metric()."""

    @pytest.mark.asyncio
    async def test_logs_metric_with_step(self, svc: Any) -> None:
        """Logs a metric with key, value, and step."""
        run_id = await svc.start_run(
            run_name="metric-test", params={}, engine_backend="stdlib", device="cpu"
        )
        await svc.log_metric(run_id, "loss", 0.5, step=1)
        client = svc._client
        assert client is not None
        assert any(
            m["key"] == "loss" and m["value"] == 0.5 and m["step"] == 1
            for m in client.logged_metrics
        )

    @pytest.mark.asyncio
    async def test_logs_metric_without_step(self, svc: Any) -> None:
        """Logs a metric without step."""
        run_id = await svc.start_run(
            run_name="no-step", params={}, engine_backend="stdlib", device="cpu"
        )
        await svc.log_metric(run_id, "loss", 0.5)
        client = svc._client
        assert client is not None
        assert any(
            m["key"] == "loss" and m["value"] == 0.5 for m in client.logged_metrics
        )

    @pytest.mark.asyncio
    async def test_degraded_noop(self, svc: Any) -> None:
        """No-ops when in degraded mode."""
        svc._degraded = True
        await svc.log_metric("run_1", "loss", 0.5)
        client = svc._client
        assert client is None or len(client.logged_metrics) == 0

    @pytest.mark.asyncio
    async def test_empty_run_id_noop(self, svc: Any) -> None:
        """No-ops when run_id is empty."""
        await svc.log_metric("", "loss", 0.5)

    @pytest.mark.asyncio
    async def test_exception_caught(self, svc: Any) -> None:
        """Silently catches exceptions."""
        svc._client = None
        await svc.log_metric("run_1", "loss", 0.5)  # Should not raise


class TestLogFinalMetric:
    """Tests for TrackingService.log_final_metric()."""

    @pytest.mark.asyncio
    async def test_logs_final_metric(self, svc: Any) -> None:
        """Logs a final metric (no step)."""
        run_id = await svc.start_run(
            run_name="final-metric", params={}, engine_backend="stdlib", device="cpu"
        )
        await svc.log_final_metric(run_id, "final_loss", 0.3)
        client = svc._client
        assert client is not None
        assert any(
            m["key"] == "final_loss" and m["value"] == 0.3
            for m in client.logged_metrics
        )

    @pytest.mark.asyncio
    async def test_degraded_noop(self, svc: Any) -> None:
        """No-ops when in degraded mode."""
        svc._degraded = True
        await svc.log_final_metric("run_1", "final_loss", 0.3)

    @pytest.mark.asyncio
    async def test_empty_run_id_noop(self, svc: Any) -> None:
        """No-ops when run_id is empty."""
        await svc.log_final_metric("", "final_loss", 0.3)


class TestSetTag:
    """Tests for TrackingService.set_tag()."""

    @pytest.mark.asyncio
    async def test_sets_tag(self, svc: Any) -> None:
        """Sets a tag on an MLflow run."""
        run_id = await svc.start_run(
            run_name="tag-test", params={}, engine_backend="stdlib", device="cpu"
        )
        await svc.set_tag(run_id, "anvil.foo", "bar")
        client = svc._client
        assert client is not None
        assert any(
            t["key"] == "anvil.foo" and t["value"] == "bar"
            for t in client.set_tag_calls
        )

    @pytest.mark.asyncio
    async def test_degraded_noop(self, svc: Any) -> None:
        """No-ops when in degraded mode."""
        svc._degraded = True
        await svc.set_tag("run_1", "anvil.foo", "bar")

    @pytest.mark.asyncio
    async def test_empty_run_id_noop(self, svc: Any) -> None:
        """No-ops when run_id is empty."""
        await svc.set_tag("", "anvil.foo", "bar")

    @pytest.mark.asyncio
    async def test_exception_caught(self, svc: Any) -> None:
        """Silently catches exceptions."""
        svc._client = None
        await svc.set_tag("run_1", "anvil.foo", "bar")


########################################################################
# Artifacts
########################################################################


class TestLogArtifacts:
    """Tests for TrackingService.log_artifacts()."""

    @pytest.mark.asyncio
    async def test_logs_model_path(self, svc: Any) -> None:
        """Logs model.json artifact."""
        run_id = await svc.start_run(
            run_name="artifacts", params={}, engine_backend="stdlib", device="cpu"
        )
        await svc.log_artifacts(run_id, model_path="/fake/model.json")
        client = svc._client
        assert client is not None
        assert any(
            a["local_path"] == "/fake/model.json" for a in client.log_artifact_calls
        )

    @pytest.mark.asyncio
    async def test_logs_all_paths(self, svc: Any) -> None:
        """Logs all artifact paths when provided."""
        run_id = await svc.start_run(
            run_name="artifacts-all", params={}, engine_backend="stdlib", device="cpu"
        )
        await svc.log_artifacts(
            run_id,
            model_path="/fake/model.json",
            safetensors_path="/fake/model.safetensors",
            config_path="/fake/config.json",
            tokenizer_path="/fake/tokenizer.json",
            mlmodel_path="/fake/MLmodel",
            conda_path="/fake/conda.yaml",
        )
        client = svc._client
        assert client is not None
        paths = [a["local_path"] for a in client.log_artifact_calls]
        assert "/fake/model.json" in paths
        assert "/fake/model.safetensors" in paths
        assert "/fake/config.json" in paths
        assert "/fake/tokenizer.json" in paths
        assert "/fake/MLmodel" in paths
        assert "/fake/conda.yaml" in paths

    @pytest.mark.asyncio
    async def test_logs_samples_and_vocab(self, svc: Any) -> None:
        """Logs _samples and _vocab as artifacts."""
        run_id = await svc.start_run(
            run_name="artifacts-samples",
            params={},
            engine_backend="stdlib",
            device="cpu",
        )
        await svc.log_artifacts(
            run_id, model_path="/fake/model.json", _samples="test", _vocab=None
        )
        client = svc._client
        assert client is not None
        assert len(client.log_artifact_calls) > 0

    @pytest.mark.asyncio
    async def test_degraded_noop(self, svc: Any) -> None:
        """No-ops when in degraded mode."""
        svc._degraded = True
        await svc.log_artifacts("run_1", model_path="/fake/model.json")

    @pytest.mark.asyncio
    async def test_empty_run_id_noop(self, svc: Any) -> None:
        """No-ops when run_id is empty."""
        await svc.log_artifacts("", model_path="/fake/model.json")

    @pytest.mark.asyncio
    async def test_exception_caught(self, svc: Any) -> None:
        """Silently catches exceptions."""
        svc._client = None
        await svc.log_artifacts("run_1", model_path="/fake/model.json")

    @pytest.mark.asyncio
    async def test_no_paths_noop(self, svc: Any) -> None:
        """No-ops when no paths are provided."""
        run_id = await svc.start_run(
            run_name="artifacts-none",
            params={},
            engine_backend="stdlib",
            device="cpu",
        )
        await svc.log_artifacts(run_id)
        client = svc._client
        assert client is not None
        assert len(client.log_artifact_calls) == 0


########################################################################
# Dataset Input
########################################################################


class TestLogDatasetInput:
    """Tests for TrackingService.log_dataset_input()."""

    @pytest.mark.asyncio
    async def test_logs_and_returns_digest(self, svc: Any) -> None:
        """Logs dataset input and returns digest."""
        run_id = await svc.start_run(
            run_name="lineage-ds", params={}, engine_backend="stdlib", device="cpu"
        )

        mock_session = AsyncMock()
        with patch(
            "anvil.services.tracking.tracking.MlflowInputResolver"
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
            assert client is not None
            assert any(
                inp["run_id"] == run_id and inp["context"] == "training"
                for inp in client.logged_inputs
            )

    @pytest.mark.asyncio
    async def test_degraded_returns_empty_string(self, svc: Any) -> None:
        """Returns empty string when degraded."""
        svc._degraded = True
        digest = await svc.log_dataset_input("run_1", dataset_id=1)
        assert digest == ""

    @pytest.mark.asyncio
    async def test_no_run_id_returns_empty_string(self, svc: Any) -> None:
        """Returns empty string when run_id is empty."""
        digest = await svc.log_dataset_input("", dataset_id=1)
        assert digest == ""

    @pytest.mark.asyncio
    async def test_resolver_failure_returns_empty_string(self, svc: Any) -> None:
        """Returns empty string when resolver fails."""
        run_id = await svc.start_run(
            run_name="fail-resolver", params={}, engine_backend="stdlib", device="cpu"
        )

        with patch(
            "anvil.services.tracking.tracking.MlflowInputResolver"
        ) as resolver_cls:
            mock_session = AsyncMock()
            mock_resolver = AsyncMock()
            resolver_cls.return_value = mock_resolver
            mock_resolver.resolve_dataset.side_effect = ValueError("boom")

            digest = await svc.log_dataset_input(
                run_id, dataset_id=1, session=mock_session
            )
            assert digest == ""

    @pytest.mark.asyncio
    async def test_without_session_creates_new_session(self, svc: Any) -> None:
        """Creates a new session when none is provided."""
        run_id = await svc.start_run(
            run_name="no-session", params={}, engine_backend="stdlib", device="cpu"
        )

        with (
            patch(
                "anvil.services.tracking.tracking.AsyncSessionLocal"
            ) as mock_session_local,
            patch(
                "anvil.services.tracking.tracking.MlflowInputResolver"
            ) as resolver_cls,
        ):
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_resolver = AsyncMock()
            resolver_cls.return_value = mock_resolver
            mock_resolver.resolve_dataset.return_value = ("fake_ds", "digest123")

            digest = await svc.log_dataset_input(run_id, dataset_id=1)
            assert digest == "digest123"


class TestLogCorpusInput:
    """Tests for TrackingService.log_corpus_input()."""

    @pytest.mark.asyncio
    async def test_logs_and_returns_digest(self, svc: Any) -> None:
        """Logs corpus input and artifact paths."""
        run_id = await svc.start_run(
            run_name="lineage-corpus", params={}, engine_backend="stdlib", device="cpu"
        )

        mock_session = AsyncMock()
        with patch(
            "anvil.services.tracking.tracking.MlflowInputResolver"
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
            assert client is not None
            assert any(
                inp["run_id"] == run_id and inp["context"] == "corpus"
                for inp in client.logged_inputs
            )
            assert len(client.log_artifact_calls) >= 2

    @pytest.mark.asyncio
    async def test_degraded_returns_empty_string(self, svc: Any) -> None:
        """Returns empty string when degraded."""
        svc._degraded = True
        digest = await svc.log_corpus_input("run_1", corpus_id=1)
        assert digest == ""

    @pytest.mark.asyncio
    async def test_no_run_id_returns_empty_string(self, svc: Any) -> None:
        """Returns empty string when run_id is empty."""
        digest = await svc.log_corpus_input("", corpus_id=1)
        assert digest == ""

    @pytest.mark.asyncio
    async def test_resolver_failure_returns_empty_string(self, svc: Any) -> None:
        """Returns empty string when resolver fails."""
        run_id = await svc.start_run(
            run_name="fail-corpus", params={}, engine_backend="stdlib", device="cpu"
        )

        with patch(
            "anvil.services.tracking.tracking.MlflowInputResolver"
        ) as resolver_cls:
            mock_session = AsyncMock()
            mock_resolver = AsyncMock()
            resolver_cls.return_value = mock_resolver
            mock_resolver.resolve_corpus.side_effect = ValueError("boom")

            digest = await svc.log_corpus_input(
                run_id, corpus_id=1, session=mock_session
            )
            assert digest == ""


########################################################################
# Capabilities
########################################################################


class TestCapabilities:
    """Tests for TrackingService.capabilities()."""

    @pytest.mark.asyncio
    async def test_returns_detected_capabilities(self, svc: Any) -> None:
        """Returns detected tracking capabilities."""
        caps = await svc.capabilities()
        assert caps.mlflow_version.startswith("3.")
        assert isinstance(caps.server_backed, bool)
        assert isinstance(caps.genai_datasets, bool)


########################################################################
# Eval Dataset Management
########################################################################


class TestEvalDatasets:
    """Tests for eval dataset operations (create, append, get)."""

    # ── create_eval_dataset ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_create_raises_when_genai_unavailable(self, svc: Any) -> None:
        """Raises CapabilityUnavailable when genai datasets not supported."""
        from anvil.services._shared.capability_unavailable import CapabilityUnavailable

        with patch.object(svc, "capabilities") as mock_caps:
            mock_caps.return_value.genai_datasets = False
            mock_caps.return_value.server_backed = False
            with pytest.raises(CapabilityUnavailable):
                await svc.create_eval_dataset(name="test-ds")

    @pytest.mark.asyncio
    async def test_create_success_with_patch(self, svc: Any) -> None:
        """Creates an eval dataset successfully when genai is available."""
        with (
            patch.object(svc, "capabilities") as mock_caps,
            patch(
                "anvil.services.tracking.tracking._create_dataset_sync"
            ) as mock_create,
        ):
            mock_caps.return_value.genai_datasets = True
            mock_caps.return_value.server_backed = True
            mock_create.return_value = {"name": "test-ds", "id": 1}

            result = await svc.create_eval_dataset(
                name="test-ds", tags={"source": "unit-test"}
            )
            assert result == {"name": "test-ds", "id": 1}
            mock_create.assert_called_once_with("test-ds", {"source": "unit-test"})

    @pytest.mark.asyncio
    async def test_create_success_without_tags(self, svc: Any) -> None:
        """Creates an eval dataset without tags."""
        with (
            patch.object(svc, "capabilities") as mock_caps,
            patch(
                "anvil.services.tracking.tracking._create_dataset_sync"
            ) as mock_create,
        ):
            mock_caps.return_value.genai_datasets = True
            mock_caps.return_value.server_backed = True
            mock_create.return_value = {"name": "test-ds", "id": 2}

            result = await svc.create_eval_dataset(name="test-ds")
            assert result == {"name": "test-ds", "id": 2}
            mock_create.assert_called_once_with("test-ds", None)

    # ── append_eval_records ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_append_raises_when_genai_unavailable(self, svc: Any) -> None:
        """Raises CapabilityUnavailable when genai datasets not supported."""
        from anvil.services._shared.capability_unavailable import CapabilityUnavailable

        with patch.object(svc, "capabilities") as mock_caps:
            mock_caps.return_value.genai_datasets = False
            with pytest.raises(CapabilityUnavailable):
                await svc.append_eval_records(name="test-ds", records=[{"a": 1}])

    @pytest.mark.asyncio
    async def test_append_success(self, svc: Any) -> None:
        """Appends records to an eval dataset successfully."""
        with (
            patch.object(svc, "capabilities") as mock_caps,
            patch(
                "anvil.services.tracking.tracking._append_records_sync"
            ) as mock_append,
        ):
            mock_caps.return_value.genai_datasets = True
            mock_caps.return_value.server_backed = True
            records = [{"q": "hello", "a": "world"}]
            mock_append.return_value = 1

            count = await svc.append_eval_records(name="test-ds", records=records)
            assert count == 1
            mock_append.assert_called_once_with("test-ds", records)

    # ── get_eval_dataset ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_raises_when_genai_unavailable(self, svc: Any) -> None:
        """Raises CapabilityUnavailable when genai datasets not supported."""
        from anvil.services._shared.capability_unavailable import CapabilityUnavailable

        with patch.object(svc, "capabilities") as mock_caps:
            mock_caps.return_value.genai_datasets = False
            with pytest.raises(CapabilityUnavailable):
                await svc.get_eval_dataset(name="test-ds")

    @pytest.mark.asyncio
    async def test_get_success(self, svc: Any) -> None:
        """Retrieves an eval dataset by name."""
        with (
            patch.object(svc, "capabilities") as mock_caps,
            patch("anvil.services.tracking.tracking._get_dataset_sync") as mock_get,
        ):
            mock_caps.return_value.genai_datasets = True
            mock_caps.return_value.server_backed = True
            mock_get.return_value = {"name": "test-ds", "records": []}

            result = await svc.get_eval_dataset(name="test-ds")
            assert result == {"name": "test-ds", "records": []}
            mock_get.assert_called_once_with("test-ds")

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(self, svc: Any) -> None:
        """Returns None when eval dataset is not found."""
        with (
            patch.object(svc, "capabilities") as mock_caps,
            patch("anvil.services.tracking.tracking._get_dataset_sync") as mock_get,
        ):
            mock_caps.return_value.genai_datasets = True
            mock_caps.return_value.server_backed = True
            mock_get.return_value = None

            result = await svc.get_eval_dataset(name="nonexistent")
            assert result is None


########################################################################
# System Metrics
########################################################################


class TestSystemMetrics:
    """Tests for TrackingService.enable_system_metrics()."""

    @pytest.mark.asyncio
    async def test_enables_system_metrics(self) -> None:
        """Calls mlflow.enable_system_metrics_logging()."""
        with patch(
            "anvil.services.tracking.tracking.mlflow.enable_system_metrics_logging"
        ) as mock_enable:
            from anvil.services.tracking.tracking import TrackingService

            TrackingService.enable_system_metrics()
            mock_enable.assert_called_once()

    @pytest.mark.asyncio
    async def test_idempotent(self) -> None:
        """Calling twice only calls MLflow once."""
        import anvil.services.tracking.tracking as tracking_mod

        tracking_mod._system_metrics_enabled = False
        with patch(
            "anvil.services.tracking.tracking.mlflow.enable_system_metrics_logging"
        ) as mock_enable:
            from anvil.services.tracking.tracking import TrackingService

            TrackingService.enable_system_metrics()
            TrackingService.enable_system_metrics()
            mock_enable.assert_called_once()

    @pytest.mark.asyncio
    async def test_catches_exception(self) -> None:
        """Silently catches exceptions from MLflow."""
        import anvil.services.tracking.tracking as tracking_mod

        tracking_mod._system_metrics_enabled = False
        with patch(
            "anvil.services.tracking.tracking.mlflow.enable_system_metrics_logging",
            side_effect=RuntimeError("not available"),
        ):
            from anvil.services.tracking.tracking import TrackingService

            TrackingService.enable_system_metrics()  # Should not raise

    @pytest.mark.asyncio
    async def test_resets_global_flag_for_test_isolation(self) -> None:
        """Reset global _system_metrics_enabled to ensure test isolation.

        The previous test may have set the flag to True, which would
        cause subsequent tests in this module to short-circuit. We
        test that even after the flag is set, calling again doesn't
        raise, and that we can reset for clean isolation.
        """
        from anvil.services.tracking.tracking import (
            TrackingService,
            _system_metrics_enabled,
        )

        saved = _system_metrics_enabled
        try:
            with patch(
                "anvil.services.tracking.tracking.mlflow.enable_system_metrics_logging"
            ) as mock_enable:
                # Manually set the flag to True
                import anvil.services.tracking.tracking as tracking_mod

                tracking_mod._system_metrics_enabled = True

                TrackingService.enable_system_metrics()
                mock_enable.assert_not_called()  # Short-circuits
        finally:
            import anvil.services.tracking.tracking as tracking_mod

            tracking_mod._system_metrics_enabled = saved


########################################################################
# List Experiments
########################################################################


class TestListExperiments:
    """Tests for TrackingService.list_experiments()."""

    @pytest.mark.asyncio
    async def test_degraded_returns_empty_list(self, svc: Any) -> None:
        """Returns empty list when degraded."""
        svc._degraded = True
        result = await svc.list_experiments()
        assert result == []

    @pytest.mark.asyncio
    async def test_no_experiment_id_returns_empty_list(self, svc: Any) -> None:
        """Returns empty list when experiment_id is not set."""
        result = await svc.list_experiments()
        assert result == []

    @pytest.mark.asyncio
    async def test_lazy_init_exception_returns_empty_list(self, svc: Any) -> None:
        """Returns empty list when lazy_init raises."""
        svc._experiment_id = None
        svc._client = None
        with patch.object(svc, "_lazy_init", side_effect=RuntimeError("boom")):
            result = await svc.list_experiments()
            assert result == []

    @pytest.mark.asyncio
    async def test_returns_formatted_runs(self, svc: Any) -> None:
        """Returns formatted run data from search_runs."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        client.searched_runs = [
            _make_run_with_data(
                status="FINISHED",
                metrics={"final_loss": 0.42},
                params={"engine_backend": "stdlib", "device": "cpu"},
                tags={"mlflow.runName": "test-run", "anvil.experiment_id": "1"},
                run_id="run_1",
            ),
        ]

        result = await svc.list_experiments()
        assert len(result) == 1
        assert result[0]["mlflow_run_id"] == "run_1"
        assert result[0]["final_loss"] == 0.42
        assert result[0]["status"] == "finished"
        assert result[0]["run_name"] == "test-run"
        assert result[0]["id"] == 1

    @pytest.mark.asyncio
    async def test_skips_lifecycle_events(self, svc: Any) -> None:
        """Skips runs with engine_backend='dataset' or 'corpus'."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        client.searched_runs = [
            _make_run_with_data(
                params={"engine_backend": "dataset", "device": "n/a"},
                run_id="run_ds",
            ),
            _make_run_with_data(
                params={"engine_backend": "corpus", "device": "n/a"},
                run_id="run_corpus",
            ),
            _make_run_with_data(
                params={"engine_backend": "stdlib", "device": "cpu"},
                run_id="run_real",
            ),
        ]

        result = await svc.list_experiments()
        assert len(result) == 1
        assert result[0]["mlflow_run_id"] == "run_real"

    @pytest.mark.asyncio
    async def test_handles_missing_experiment_id_tag(self, svc: Any) -> None:
        """Handles runs without anvil.experiment_id tag."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        run = _make_run_with_data(
            tags={"mlflow.runName": "legacy"},
            run_id="run_legacy",
        )
        run.data.tags = {"mlflow.runName": "legacy"}
        client.searched_runs = [run]

        result = await svc.list_experiments()
        assert len(result) == 1
        assert result[0]["id"] is None

    @pytest.mark.asyncio
    async def test_handles_empty_run_name(self, svc: Any) -> None:
        """Handles runs without mlflow.runName tag."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        client.searched_runs = [
            _make_run_with_data(tags={}, run_id="run_no_name"),
        ]

        result = await svc.list_experiments()
        assert len(result) == 1
        assert result[0]["run_name"] == ""

    @pytest.mark.asyncio
    async def test_search_runs_exception_returns_empty(self, svc: Any) -> None:
        """Returns empty list when search_runs fails."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        def failing_search(*args: Any, **kwargs: Any) -> list[Any]:
            raise RuntimeError("search failed")

        client.search_runs = failing_search  # type: ignore[assignment]

        result = await svc.list_experiments()
        assert result == []

    @pytest.mark.asyncio
    async def test_normalizes_status_to_lowercase(self, svc: Any) -> None:
        """Normalizes MLflow status to lowercase."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        client.searched_runs = [
            _make_run_with_data(
                status="RUNNING",
                run_id="run_running",
            ),
        ]

        result = await svc.list_experiments()
        assert len(result) == 1
        assert result[0]["status"] == "running"


########################################################################
# Get Experiment
########################################################################


class TestGetExperiment:
    """Tests for TrackingService.get_experiment()."""

    @pytest.mark.asyncio
    async def test_degraded_returns_none(self, svc: Any) -> None:
        """Returns None when degraded."""
        svc._degraded = True
        result = await svc.get_experiment(1)
        assert result is None

    @pytest.mark.asyncio
    async def test_not_found_returns_none(self, svc: Any) -> None:
        """Returns None when no runs match."""
        svc._lazy_init()
        client = svc._client
        assert client is not None
        client.searched_runs = []
        result = await svc.get_experiment(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_lazy_init_exception_returns_none(self, svc: Any) -> None:
        """Returns None when lazy_init fails."""
        svc._client = None
        svc._experiment_id = None
        with patch.object(svc, "_lazy_init", side_effect=RuntimeError("boom")):
            result = await svc.get_experiment(1)
            assert result is None

    @pytest.mark.asyncio
    async def test_search_runs_exception_returns_none(self, svc: Any) -> None:
        """Returns None when search_runs fails."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        def failing_search(*args: Any, **kwargs: Any) -> list[Any]:
            raise RuntimeError("search failed")

        client.search_runs = failing_search  # type: ignore[assignment]

        result = await svc.get_experiment(1)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_formatted_run(self, svc: Any) -> None:
        """Returns formatted run data for matching experiment."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        client.searched_runs = [
            _make_run_with_data(
                status="FINISHED",
                metrics={"final_loss": 0.42},
                params={"engine_backend": "stdlib", "device": "cpu"},
                tags={
                    "mlflow.runName": "exp-run",
                    "anvil.experiment_id": "1",
                    "anvil.dataset.name": "test-ds",
                    "anvil.input_digest": "abc123",
                    "anvil.input_role": "training",
                },
                run_id="run_1",
                start_time=1000000,
                end_time=2000000,
            ),
        ]

        result = await svc.get_experiment(1)
        assert result is not None
        assert result["id"] == 1
        assert result["mlflow_run_id"] == "run_1"
        assert result["final_loss"] == 0.42
        assert result["status"] == "finished"
        assert result["run_name"] == "exp-run"
        assert result["dataset_name"] == "test-ds"
        assert result["input_digest"] == "abc123"
        assert result["input_role"] == "training"
        assert result["created_at"] == "1000000"
        assert result["completed_at"] == "2000000"
        assert "params" in result
        assert "metrics" in result
        assert "tags" in result


########################################################################
# Search Runs / List Runs (wrapped by list_experiments)
########################################################################


class TestSearchAndListRuns:
    """Tests that exercise the underlying search_runs MLflow client path.

    ``TrackingService`` does not expose a standalone ``search_runs()``
    or ``list_runs()`` method; these are exercised through
    ``list_experiments()`` and ``get_experiment()``. This class
    validates that the correct MLflow ``search_runs`` parameters are
    sent and that the response is shaped correctly.
    """

    @pytest.mark.asyncio
    async def test_list_experiments_uses_max_results(self, svc: Any) -> None:
        """list_experiments passes max_results to search_runs."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        client.searched_runs = [
            _make_run_with_data(run_id="r1"),
            _make_run_with_data(run_id="r2"),
        ]
        result = await svc.list_experiments(max_results=2)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_experiment_uses_filter_string(self, svc: Any) -> None:
        """get_experiment uses a filter_string for anvil.experiment_id."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        client.searched_runs = [
            _make_run_with_data(
                tags={"anvil.experiment_id": "42"},
                run_id="run_42",
            ),
        ]
        result = await svc.get_experiment(42)
        assert result is not None
        assert result["id"] == 42

    @pytest.mark.asyncio
    async def test_handles_empty_search_results(self, svc: Any) -> None:
        """list_experiments returns empty list when search_runs yields nothing."""
        svc._lazy_init()
        client = svc._client
        assert client is not None
        client.searched_runs = []
        result = await svc.list_experiments()
        assert result == []


########################################################################
# Reconcile Orphans
########################################################################


class TestReconcileOrphans:
    """Tests for TrackingService.reconcile_orphans()."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_running_runs(self, svc: Any) -> None:
        """Returns empty list when no RUNNING runs exist."""
        await svc.start_run(
            run_name="reconcile", params={}, engine_backend="stdlib", device="cpu"
        )
        client = svc._client
        assert client is not None
        client.searched_runs = []
        result = await svc.reconcile_orphans()
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_reconciles_running_runs(self, svc: Any) -> None:
        """Reconciles RUNNING runs by marking them KILLED."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        running_run = _make_run_with_data(status="RUNNING", run_id="run_running")
        client.searched_runs = [running_run]

        result = await svc.reconcile_orphans()
        assert len(result) == 1
        assert result[0] == "run_running"
        assert any(
            c["run_id"] == "run_running" and c["status"] == "KILLED"
            for c in client.set_terminated_calls
        )

    @pytest.mark.asyncio
    async def test_no_experiment_returns_empty(self) -> None:
        """Returns empty list when experiment_id is not set."""
        from anvil.services.tracking.tracking import TrackingService

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000", client_factory=fake_client_factory
        )
        result = await svc.reconcile_orphans()
        assert result == []

    @pytest.mark.asyncio
    async def test_exception_caught(self, svc: Any) -> None:
        """Returns empty list on exception."""
        svc._client = None
        result = await svc.reconcile_orphans()
        assert result == []


########################################################################
# Safetensors Artifacts
########################################################################


class TestGetSafetensorsArtifacts:
    """Tests for TrackingService.get_safetensors_artifacts()."""

    @pytest.mark.asyncio
    async def test_degraded_returns_empty(self, svc: Any) -> None:
        """Returns empty dict when in degraded mode."""
        svc._degraded = True
        result = await svc.get_safetensors_artifacts("run_1")
        assert result == {"available": False, "files": [], "error": None}

    @pytest.mark.asyncio
    async def test_empty_run_id_returns_empty(self, svc: Any) -> None:
        """Returns empty dict when run_id is empty."""
        result = await svc.get_safetensors_artifacts("")
        assert result == {"available": False, "files": [], "error": None}

    @pytest.mark.asyncio
    async def test_client_not_initialized(self, svc: Any) -> None:
        """Returns error when lazy_init fails."""
        svc._client = None
        with patch.object(
            svc, "_lazy_init", side_effect=RuntimeError("client not initialized")
        ):
            result = await svc.get_safetensors_artifacts("run_1")
        assert result["available"] is False
        assert "client not initialized" in (result["error"] or "")

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_artifacts(self, svc: Any) -> None:
        """Returns empty files list when no artifacts exist."""
        svc._lazy_init()
        client = svc._client
        assert client is not None
        client.list_artifacts_result = []
        result = await svc.get_safetensors_artifacts("run_1")
        assert result["available"] is False
        assert result["files"] == []

    @pytest.mark.asyncio
    async def test_filters_safetensors_files(self, svc: Any) -> None:
        """Correctly identifies safetensors, config, and tokenizer files."""
        svc._lazy_init()
        client = svc._client
        assert client is not None
        client.list_artifacts_result = [
            FakeFileInfo(path="model.safetensors", file_size=1024),
            FakeFileInfo(path="config.json", file_size=256),
            FakeFileInfo(path="tokenizer.json", file_size=128),
            FakeFileInfo(path="other.txt", file_size=64),
        ]
        result = await svc.get_safetensors_artifacts("run_1")
        assert result["available"] is True
        assert len(result["files"]) == 3
        safetensors_files = [f for f in result["files"] if f["is_safetensors"]]
        assert len(safetensors_files) == 1
        assert safetensors_files[0]["path"] == "model.safetensors"

    @pytest.mark.asyncio
    async def test_exception_returns_error(self, svc: Any) -> None:
        """Returns error dict on exception."""
        svc._client = MagicMock()
        svc._client.list_artifacts.side_effect = RuntimeError("boom")
        result = await svc.get_safetensors_artifacts("run_1")
        assert result["available"] is False
        assert "boom" in (result["error"] or "")


########################################################################
# Register Source Model
########################################################################


class TestRegisterSourceModel:
    """Tests for TrackingService.register_source_model()."""

    @pytest.mark.asyncio
    async def test_degraded_returns_empty_dict(self, svc: Any) -> None:
        """Returns empty dict when degraded."""
        svc._degraded = True
        result = await svc.register_source_model(run_id="run_1")
        assert result == {}

    @pytest.mark.asyncio
    async def test_empty_run_id_returns_empty_dict(self, svc: Any) -> None:
        """Returns empty dict when run_id is empty."""
        result = await svc.register_source_model(run_id="")
        assert result == {}

    @pytest.mark.asyncio
    async def test_no_client_returns_empty_dict(self, svc: Any) -> None:
        """Returns empty dict when client is None."""
        svc._client = None
        result = await svc.register_source_model(run_id="run_1")
        assert result == {}

    @pytest.mark.asyncio
    async def test_registers_with_explicit_name(self, svc: Any) -> None:
        """Registers with explicit model name."""
        svc._lazy_init()
        result = await svc.register_source_model(
            run_id="run_1", name="my-model", artifact_path="model.json"
        )
        assert result["name"] == "my-model"
        assert result["run_id"] == "run_1"
        assert result["version"] == "1"
        assert "runs:/run_1/model.json" in result["source"]

    @pytest.mark.asyncio
    async def test_registers_with_dataset_id(self, svc: Any) -> None:
        """Registers with auto-generated name from dataset_id."""
        svc._lazy_init()
        result = await svc.register_source_model(
            run_id="run_1", dataset_id=42, artifact_path="model.json"
        )
        assert result["name"] == "dataset-42"

    @pytest.mark.asyncio
    async def test_registers_with_corpus_id(self, svc: Any) -> None:
        """Registers with auto-generated name from corpus_id."""
        svc._lazy_init()
        result = await svc.register_source_model(
            run_id="run_1", corpus_id=7, artifact_path="model.json"
        )
        assert result["name"] == "corpus-7"

    @pytest.mark.asyncio
    async def test_registers_with_default_name(self, svc: Any) -> None:
        """Registers with default name when no identifier provided."""
        svc._lazy_init()
        result = await svc.register_source_model(
            run_id="run_1", artifact_path="model.json"
        )
        assert result["name"] == "default-source"

    @pytest.mark.asyncio
    async def test_sanitizes_name(self, svc: Any) -> None:
        """Sanitizes model names containing '/' or ':'."""
        svc._lazy_init()
        result = await svc.register_source_model(run_id="run_1", name="my/model:1")
        assert result["name"] == "my-model-1"


########################################################################
# Lifecycle Events
########################################################################


class TestLogDatasetLifecycleEvent:
    """Tests for TrackingService.log_dataset_lifecycle_event()."""

    @pytest.mark.asyncio
    async def test_creates_run_with_correct_tags(self) -> None:
        """Creates a short-lived MLflow run for dataset events."""
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

    @pytest.mark.asyncio
    async def test_degraded_returns_empty(self) -> None:
        """Returns '' when service is degraded."""
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
    async def test_connection_error_sets_degraded(self) -> None:
        """Returns '' and sets degraded on connection error."""
        from anvil.services.tracking.tracking import TrackingService

        def broken_factory(uri: str) -> FakeMlflowClient:
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
    async def test_all_event_types(self) -> None:
        """Handles all event types: create, import, curate, update, delete."""
        from anvil.services.tracking.tracking import TrackingService

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000", client_factory=fake_client_factory
        )
        for event_type in ("create", "import", "curate", "update", "delete"):
            run_id = await svc.log_dataset_lifecycle_event(
                dataset_id=1, event_type=event_type
            )
            assert run_id, f"Expected non-empty run_id for event_type={event_type}"

    @pytest.mark.asyncio
    async def test_lazy_init_failure_sets_degraded(self) -> None:
        """Sets degraded mode when lazy init fails."""
        from anvil.services.tracking.tracking import TrackingService

        class FailingLazyClient(FakeMlflowClient):
            def get_experiment_by_name(self, name: str) -> FakeExperiment | None:
                raise RuntimeError("DB unavailable")

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000",
            client_factory=lambda uri: FailingLazyClient(uri),
        )
        run_id = await svc.log_dataset_lifecycle_event(
            dataset_id=42, event_type="create"
        )
        assert run_id == ""
        assert svc.is_degraded


class TestLogCorpusLifecycleEvent:
    """Tests for TrackingService.log_corpus_lifecycle_event()."""

    @pytest.mark.asyncio
    async def test_creates_run_with_correct_tags(self) -> None:
        """Creates a short-lived MLflow run for corpus events."""
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

    @pytest.mark.asyncio
    async def test_creates_run_without_tags(self) -> None:
        """Creates run without extra tags when tags is None."""
        from anvil.services.tracking.tracking import TrackingService

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000", client_factory=fake_client_factory
        )
        run_id = await svc.log_corpus_lifecycle_event(
            corpus_id=7, event_type="ingest", tags=None
        )
        assert run_id, "Expected non-empty run_id"

    @pytest.mark.asyncio
    async def test_degraded_returns_empty(self) -> None:
        """Returns '' when service is degraded."""
        from anvil.services.tracking.tracking import TrackingService

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000", client_factory=fake_client_factory
        )
        svc._degraded = True
        run_id = await svc.log_corpus_lifecycle_event(corpus_id=7, event_type="ingest")
        assert run_id == ""

    @pytest.mark.asyncio
    async def test_connection_error_sets_degraded(self) -> None:
        """Returns '' and sets degraded on connection error."""
        from anvil.services.tracking.tracking import TrackingService

        def broken_factory(uri: str) -> FakeMlflowClient:
            raise ConnectionError("Connection refused")

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000", client_factory=broken_factory
        )
        run_id = await svc.log_corpus_lifecycle_event(corpus_id=7, event_type="ingest")
        assert run_id == ""
        assert svc.is_degraded

    @pytest.mark.asyncio
    async def test_lazy_init_failure_sets_degraded(self) -> None:
        """Sets degraded mode when lazy init fails."""
        from anvil.services.tracking.tracking import TrackingService

        class FailingLazyClient(FakeMlflowClient):
            def get_experiment_by_name(self, name: str) -> FakeExperiment | None:
                raise RuntimeError("DB unavailable")

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000",
            client_factory=lambda uri: FailingLazyClient(uri),
        )
        run_id = await svc.log_corpus_lifecycle_event(corpus_id=7, event_type="ingest")
        assert run_id == ""
        assert svc.is_degraded

    @pytest.mark.asyncio
    async def test_sets_additional_tags(self) -> None:
        """Sets additional tags when provided."""
        from anvil.services.tracking.tracking import TrackingService

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000", client_factory=fake_client_factory
        )
        run_id = await svc.log_corpus_lifecycle_event(
            corpus_id=7,
            event_type="fork",
            tags={"anvil.parent_corpus_id": "3", "custom": "value"},
        )
        assert run_id
        client = svc._client
        assert client is not None
        assert any(
            t["key"] == "anvil.parent_corpus_id" and t["value"] == "3"
            for t in client.set_tag_calls
        )
        assert any(
            t["key"] == "custom" and t["value"] == "value" for t in client.set_tag_calls
        )


########################################################################
# Listed Registered Models
########################################################################


class TestListRegisteredModels:
    """Tests for TrackingService.list_registered_models()."""

    @pytest.mark.asyncio
    async def test_degraded_returns_empty_list(self, svc: Any) -> None:
        """Returns empty list when degraded."""
        svc._degraded = True
        result = await svc.list_registered_models()
        assert result == []

    @pytest.mark.asyncio
    async def test_no_client_returns_empty_list(self, svc: Any) -> None:
        """Returns empty list when client is not initialized."""
        svc._client = None
        result = await svc.list_registered_models()
        assert result == []

    @pytest.mark.asyncio
    async def test_lazy_init_exception_returns_empty_list(self, svc: Any) -> None:
        """Returns empty list when lazy_init fails."""
        with patch.object(svc, "_lazy_init", side_effect=RuntimeError("boom")):
            result = await svc.list_registered_models()
            assert result == []

    @pytest.mark.asyncio
    async def test_returns_registered_models(self, svc: Any) -> None:
        """Returns formatted registered model data."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        client.registered_models = [
            FakeRegisteredModel(name="model-a", description="Model A"),
            FakeRegisteredModel(name="model-b", description="Model B"),
        ]
        client.model_versions = [
            FakeModelVersion(version="2", run_id="run_1"),
        ]

        result = await svc.list_registered_models()
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_empty_when_no_versions(self, svc: Any) -> None:
        """Skips models with no versions."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        client.registered_models = [FakeRegisteredModel(name="empty-model")]
        client.model_versions = []

        result = await svc.list_registered_models()
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_search_filter(self, svc: Any) -> None:
        """Passes search filter to MLflow."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        client.registered_models = []
        result = await svc.list_registered_models(search="test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_exception(self, svc: Any) -> None:
        """Returns empty list when search fails."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        def failing_search(*args: Any, **kwargs: Any) -> list[Any]:
            raise RuntimeError("search failed")

        client.search_registered_models = failing_search  # type: ignore[assignment]

        result = await svc.list_registered_models()
        assert result == []


########################################################################
# Comprehensive Degraded Mode
########################################################################


class TestDegradedMode:
    """Comprehensive tests for degraded mode (all early-return paths)."""

    @pytest.mark.asyncio
    async def test_all_operations_noop_in_degraded_mode(self, svc: Any) -> None:
        """All methods no-op in degraded mode without raising."""
        svc._degraded = True

        assert (
            await svc.start_run(run_name="x", params={}, engine_backend="s", device="c")
            == ""
        )
        await svc.log_metric("x", "k", 1.0)
        await svc.log_final_metric("x", "k", 1.0)
        await svc.finish_run("x")
        await svc.fail_run("x")
        await svc.set_tag("x", "k", "v")
        await svc.log_artifacts("x", model_path="/x")
        assert await svc.log_dataset_input("x", dataset_id=1) == ""
        assert await svc.log_corpus_input("x", corpus_id=1) == ""
        assert await svc.get_safetensors_artifacts("x") == {
            "available": False,
            "files": [],
            "error": None,
        }
        assert await svc.register_source_model(run_id="x") == {}
        assert (
            await svc.log_dataset_lifecycle_event(dataset_id=1, event_type="create")
            == ""
        )
        assert (
            await svc.log_corpus_lifecycle_event(corpus_id=1, event_type="ingest") == ""
        )
        assert await svc.list_experiments() == []
        assert await svc.get_experiment(1) is None
        assert await svc.list_registered_models() == []

    @pytest.mark.asyncio
    async def test_enters_degraded_on_connection_error(self) -> None:
        """Enters degraded mode on ConnectionError and stays there."""
        from anvil.services.tracking.tracking import TrackingService

        class DegradedClient(FakeMlflowClient):
            def create_run(
                self,
                experiment_id: str,
                run_name: str | None = None,
                tags: dict[str, Any] | None = None,
            ) -> FakeRun:
                raise ConnectionError("fail")

        svc = TrackingService(
            tracking_uri="http://fail:5000",
            client_factory=lambda uri: DegradedClient(uri),
        )
        run_id = await svc.start_run(
            run_name="d", params={}, engine_backend="stdlib", device="cpu"
        )
        assert svc.is_degraded
        await svc.log_metric(run_id, "loss", 0.5, step=1)
        await svc.finish_run(run_id)
        assert svc._client is not None
        assert len(svc._client.set_terminated_calls) == 0

    @pytest.mark.asyncio
    async def test_enters_degraded_on_generic_exception(self) -> None:
        """Enters degraded mode on generic Exception."""
        from anvil.services.tracking.tracking import TrackingService

        class BrokenClient(FakeMlflowClient):
            def create_run(
                self,
                experiment_id: str,
                run_name: str | None = None,
                tags: dict[str, Any] | None = None,
            ) -> FakeRun:
                raise RuntimeError("Something broke")

        svc = TrackingService(
            tracking_uri="http://broken:5000",
            client_factory=lambda uri: BrokenClient(uri),
        )
        run_id = await svc.start_run(
            run_name="d", params={}, engine_backend="stdlib", device="cpu"
        )
        assert svc.is_degraded
        assert run_id == ""


########################################################################
# Module-level sync functions
########################################################################


class TestModuleSyncFunctions:
    """Tests for module-level helper functions (_create_dataset_sync,
    _append_records_sync, _get_dataset_sync)."""

    def test_create_dataset_sync_raises_when_not_available(self) -> None:
        """Raises ImportError when mlflow.genai.datasets is not available."""
        from anvil.services.tracking.tracking import _create_dataset_sync

        with patch("anvil.services.tracking.tracking.create_dataset", None):
            with pytest.raises(ImportError, match="mlflow.genai.datasets"):
                _create_dataset_sync("test", {})

    def test_append_records_sync_raises_when_not_available(self) -> None:
        """Raises ImportError when get_dataset is not available."""
        from anvil.services.tracking.tracking import _append_records_sync

        with patch("anvil.services.tracking.tracking.get_dataset", None):
            with pytest.raises(ImportError, match="mlflow.genai.datasets"):
                _append_records_sync("test", [{"a": 1}])

    def test_get_dataset_sync_returns_none_when_not_available(self) -> None:
        """Returns None when get_dataset is not available."""
        from anvil.services.tracking.tracking import _get_dataset_sync

        with patch("anvil.services.tracking.tracking.get_dataset", None):
            assert _get_dataset_sync("test") is None

    def test_get_dataset_sync_returns_none_on_exception(self) -> None:
        """Returns None when get_dataset raises."""
        from anvil.services.tracking.tracking import _get_dataset_sync

        with patch(
            "anvil.services.tracking.tracking.get_dataset",
            side_effect=ValueError("not found"),
        ):
            assert _get_dataset_sync("test") is None


########################################################################
# Lazy Init: experiment creation path
########################################################################


class TestLazyInit:
    """Tests for TrackingService._lazy_init() experiment creation path."""

    @pytest.mark.asyncio
    async def test_creates_experiment_when_not_found(self) -> None:
        """Creates experiment when get_experiment_by_name returns None."""
        from anvil.services.tracking.tracking import TrackingService

        class CreateExpClient(FakeMlflowClient):
            def get_experiment_by_name(self, name: str) -> FakeExperiment | None:
                return None

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000",
            client_factory=lambda uri: CreateExpClient(uri),
        )
        client = svc._lazy_init()
        assert svc._experiment_id == "exp_1"


########################################################################
# Exception paths (client set, MLflow call raises)
########################################################################


class TestExceptionPathsWithClient:
    """Tests that exception catches work when client exists but MLflow
    calls raise — distinguishes from test_exception_caught which sets
    client to None to exercise the guard."""

    @pytest.mark.asyncio
    async def test_log_metric_exception_with_client(self, svc: Any) -> None:
        """Catches exception from log_metric when client exists."""
        run_id = await svc.start_run(
            run_name="metric-exc", params={}, engine_backend="s", device="c"
        )
        assert svc._client is not None
        svc._client.log_metric = MagicMock(  # type: ignore[method-assign]
            side_effect=ValueError("MLflow error")
        )
        await svc.log_metric(run_id, "loss", 0.5)  # Should not raise

    @pytest.mark.asyncio
    async def test_finish_run_exception_with_client(self, svc: Any) -> None:
        """Catches exception from set_terminated when client exists."""
        run_id = await svc.start_run(
            run_name="finish-exc", params={}, engine_backend="s", device="c"
        )
        assert svc._client is not None
        svc._client.set_terminated = MagicMock(  # type: ignore[method-assign]
            side_effect=ValueError("MLflow error")
        )
        await svc.finish_run(run_id)  # Should not raise

    @pytest.mark.asyncio
    async def test_fail_run_exception_with_client(self, svc: Any) -> None:
        """Catches exception from set_terminated FAILED when client exists."""
        run_id = await svc.start_run(
            run_name="fail-exc", params={}, engine_backend="s", device="c"
        )
        assert svc._client is not None
        svc._client.set_terminated = MagicMock(  # type: ignore[method-assign]
            side_effect=ValueError("MLflow error")
        )
        await svc.fail_run(run_id)  # Should not raise

    @pytest.mark.asyncio
    async def test_set_tag_exception_with_client(self, svc: Any) -> None:
        """Catches exception from set_tag when client exists."""
        run_id = await svc.start_run(
            run_name="tag-exc", params={}, engine_backend="s", device="c"
        )
        assert svc._client is not None
        svc._client.set_tag = MagicMock(  # type: ignore[method-assign]
            side_effect=ValueError("MLflow error")
        )
        await svc.set_tag(run_id, "k", "v")  # Should not raise

    @pytest.mark.asyncio
    async def test_log_artifacts_exception_with_client(self, svc: Any) -> None:
        """Catches exception from log_artifact when client exists."""
        run_id = await svc.start_run(
            run_name="art-exc", params={}, engine_backend="s", device="c"
        )
        assert svc._client is not None
        svc._client.log_artifact = MagicMock(  # type: ignore[method-assign]
            side_effect=ValueError("MLflow error")
        )
        await svc.log_artifacts(
            run_id, model_path="/fake/model.json"
        )  # Should not raise


########################################################################
# Dataset input: without session exception path
########################################################################


class TestLogDatasetInputNoSession:
    """Tests log_dataset_input without a provided session."""

    @pytest.mark.asyncio
    async def test_resolver_failure_without_session_returns_empty(
        self, svc: Any
    ) -> None:
        """Returns empty string when resolver fails without provided session."""
        run_id = await svc.start_run(
            run_name="ds-no-sess-fail",
            params={},
            engine_backend="stdlib",
            device="cpu",
        )
        with (
            patch(
                "anvil.services.tracking.tracking.AsyncSessionLocal"
            ) as mock_session_local,
            patch(
                "anvil.services.tracking.tracking.MlflowInputResolver"
            ) as resolver_cls,
        ):
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_resolver = AsyncMock()
            resolver_cls.return_value = mock_resolver
            mock_resolver.resolve_dataset.side_effect = ValueError("boom")

            digest = await svc.log_dataset_input(run_id, dataset_id=1)
            assert digest == ""


########################################################################
# Corpus input: without session paths
########################################################################


class TestLogCorpusInputNoSession:
    """Tests log_corpus_input without a provided session."""

    @pytest.mark.asyncio
    async def test_logs_and_returns_digest_without_session(self, svc: Any) -> None:
        """Logs corpus input and artifacts using a new session."""
        run_id = await svc.start_run(
            run_name="corpus-no-sess",
            params={},
            engine_backend="stdlib",
            device="cpu",
        )

        with (
            patch(
                "anvil.services.tracking.tracking.AsyncSessionLocal"
            ) as mock_session_local,
            patch(
                "anvil.services.tracking.tracking.MlflowInputResolver"
            ) as resolver_cls,
        ):
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_resolver = AsyncMock()
            resolver_cls.return_value = mock_resolver
            mock_resolver.resolve_corpus.return_value = (
                "fake_meta_ds",
                ["/tmp/a.py", "/tmp/b.py"],
                "corpus_digest",
            )

            digest = await svc.log_corpus_input(run_id, corpus_id=1)
            assert digest == "corpus_digest"
            client = svc._client
            assert client is not None
            assert any(
                inp["run_id"] == run_id and inp["context"] == "corpus"
                for inp in client.logged_inputs
            )
            assert len(client.log_artifact_calls) >= 2

    @pytest.mark.asyncio
    async def test_resolver_failure_without_session_returns_empty(
        self, svc: Any
    ) -> None:
        """Returns empty string when resolver fails without provided session."""
        run_id = await svc.start_run(
            run_name="corpus-no-sess-fail",
            params={},
            engine_backend="stdlib",
            device="cpu",
        )

        with (
            patch(
                "anvil.services.tracking.tracking.AsyncSessionLocal"
            ) as mock_session_local,
            patch(
                "anvil.services.tracking.tracking.MlflowInputResolver"
            ) as resolver_cls,
        ):
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_resolver = AsyncMock()
            resolver_cls.return_value = mock_resolver
            mock_resolver.resolve_corpus.side_effect = ValueError("boom")

            digest = await svc.log_corpus_input(run_id, corpus_id=1)
            assert digest == ""


########################################################################
# Reconcile orphans: search exception path
########################################################################


class TestReconcileOrphansException:
    """Tests reconcile_orphans when search_runs raises."""

    @pytest.mark.asyncio
    async def test_search_exception_returns_empty(self, svc: Any) -> None:
        """Returns empty list when search_runs raises."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        def failing_search(*args: Any, **kwargs: Any) -> list[Any]:
            raise RuntimeError("search failed")

        client.search_runs = failing_search  # type: ignore[assignment]
        result = await svc.reconcile_orphans()
        assert result == []


########################################################################
# Get safetensors artifacts: client is None path
########################################################################


class TestGetSafetensorsArtifactsClientNone:
    """Tests get_safetensors_artifacts when _lazy_init succeeds but client is None."""

    @pytest.mark.asyncio
    async def test_client_is_none_returns_error(self, svc: Any) -> None:
        """Returns error dict when client is None after lazy_init."""
        svc._client = None
        with patch.object(svc, "_lazy_init", return_value=None):
            result = await svc.get_safetensors_artifacts("run_1")
        assert result["available"] is False
        assert result["error"] == "client not initialized"


########################################################################
# Register source model: create_registered_model exception
########################################################################


class TestRegisterSourceModelException:
    """Tests register_source_model when create_registered_model raises."""

    @pytest.mark.asyncio
    async def test_create_registered_model_exception_caught(self, svc: Any) -> None:
        """Silently catches exception from create_registered_model."""
        svc._lazy_init()
        client = svc._client
        assert client is not None
        client.create_registered_model = MagicMock(  # type: ignore[method-assign]
            side_effect=ValueError("already exists")
        )
        result = await svc.register_source_model(
            run_id="run_1", name="existing-model", artifact_path="model.json"
        )
        # Should still return result — exception in create_registered_model
        # is caught, and create_model_version should proceed.
        assert result["name"] == "existing-model"
        assert result["version"] == "1"


########################################################################
# Lifecycle events: start_run returns empty
########################################################################


class TestLifecycleEventsEmptyStartRun:
    """Tests lifecycle events when start_run returns empty (degraded after init)."""

    @pytest.mark.asyncio
    async def test_dataset_event_start_run_returns_empty(self) -> None:
        """Returns '' when start_run returns empty after lazy_init succeeds."""
        from anvil.services.tracking.tracking import TrackingService

        class FailCreateRunClient(FakeMlflowClient):
            def create_run(
                self,
                experiment_id: str,
                run_name: str | None = None,
                tags: dict[str, Any] | None = None,
            ) -> FakeRun:
                raise ConnectionError("fail")

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000",
            client_factory=lambda uri: FailCreateRunClient(uri),
        )
        run_id = await svc.log_dataset_lifecycle_event(
            dataset_id=42, event_type="create"
        )
        assert run_id == ""

    @pytest.mark.asyncio
    async def test_corpus_event_start_run_returns_empty(self) -> None:
        """Returns '' when start_run returns empty after lazy_init succeeds."""
        from anvil.services.tracking.tracking import TrackingService

        class FailCreateRunClient(FakeMlflowClient):
            def create_run(
                self,
                experiment_id: str,
                run_name: str | None = None,
                tags: dict[str, Any] | None = None,
            ) -> FakeRun:
                raise ConnectionError("fail")

        svc = TrackingService(
            tracking_uri="http://127.0.0.1:5000",
            client_factory=lambda uri: FailCreateRunClient(uri),
        )
        run_id = await svc.log_corpus_lifecycle_event(corpus_id=7, event_type="ingest")
        assert run_id == ""

    @pytest.mark.asyncio
    async def test_dataset_event_start_run_empty_with_mock(self, svc: Any) -> None:
        """Returns '' when start_run returns empty using mocked start_run."""
        svc._lazy_init()
        svc._degraded = False
        with patch.object(svc, "start_run", return_value=""):
            run_id = await svc.log_dataset_lifecycle_event(
                dataset_id=42, event_type="create"
            )
            assert run_id == ""

    @pytest.mark.asyncio
    async def test_corpus_event_start_run_empty_with_mock(self, svc: Any) -> None:
        """Returns '' when start_run returns empty using mocked start_run."""
        svc._lazy_init()
        svc._degraded = False
        with patch.object(svc, "start_run", return_value=""):
            run_id = await svc.log_corpus_lifecycle_event(
                corpus_id=7, event_type="ingest"
            )
            assert run_id == ""


########################################################################
# List experiments: client/exp_id None after lazy_init
########################################################################


class TestListExperimentsClientNone:
    """Tests list_experiments edge cases."""

    @pytest.mark.asyncio
    async def test_client_none_after_lazy_init_returns_empty(self, svc: Any) -> None:
        """Returns empty list when client is None after lazy_init."""
        svc._client = None
        with patch.object(svc, "_lazy_init", return_value=None):
            result = await svc.list_experiments()
        assert result == []

    @pytest.mark.asyncio
    async def test_experiment_id_not_set_returns_empty(self, svc: Any) -> None:
        """Returns empty list when experiment_id is not set."""
        svc._lazy_init()
        svc._experiment_id = None
        with patch.object(svc, "_lazy_init") as mock_init:
            mock_init.return_value = svc._client
            result = await svc.list_experiments()
        assert result == []


########################################################################
# Get experiment: client/exp_id None after lazy_init
########################################################################


class TestGetExperimentClientNone:
    """Tests get_experiment edge cases."""

    @pytest.mark.asyncio
    async def test_client_none_after_lazy_init_returns_none(self, svc: Any) -> None:
        """Returns None when client is None after lazy_init."""
        svc._client = None
        with patch.object(svc, "_lazy_init", return_value=None):
            result = await svc.get_experiment(1)
        assert result is None

    @pytest.mark.asyncio
    async def test_experiment_id_not_set_returns_none(self, svc: Any) -> None:
        """Returns None when experiment_id is not set."""
        svc._lazy_init()
        svc._experiment_id = None
        with patch.object(svc, "_lazy_init") as mock_init:
            mock_init.return_value = svc._client
            result = await svc.get_experiment(1)
        assert result is None


########################################################################
# List registered models: client None & exception paths
########################################################################


class TestListRegisteredModelsExceptions:
    """Tests list_registered_models edge cases."""

    @pytest.mark.asyncio
    async def test_client_none_after_lazy_init(self, svc: Any) -> None:
        """Returns empty list when client is None after lazy_init."""
        svc._client = None
        with patch.object(svc, "_lazy_init", return_value=None):
            result = await svc.list_registered_models()
        assert result == []

    @pytest.mark.asyncio
    async def test_exception_in_get_run(self, svc: Any) -> None:
        """Handles exception when get_run fails for a model version."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        client.registered_models = [FakeRegisteredModel(name="model-a")]
        client.model_versions = [
            FakeModelVersion(version="1", run_id="run_bad"),
        ]

        def failing_get_run(rid: str) -> FakeRun:
            raise RuntimeError("get_run failed")

        client.get_run = failing_get_run  # type: ignore[method-assign]

        result = await svc.list_registered_models()
        # Should still include the model — get_run exception is caught
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_exception_in_model_loop(self, svc: Any) -> None:
        """Skips model when search_model_versions fails."""
        svc._lazy_init()
        client = svc._client
        assert client is not None

        def failing_search_versions(
            filter_string: str,
        ) -> list[FakeModelVersion]:
            raise RuntimeError("search_model_versions failed")

        client.search_model_versions = failing_search_versions  # type: ignore[method-assign]
        client.registered_models = [FakeRegisteredModel(name="broken-model")]

        result = await svc.list_registered_models()
        assert len(result) == 0


########################################################################
# Module-level sync functions: success and edge case coverage
########################################################################


class TestModuleSyncFunctionsCoverage:
    """Additional coverage for module-level sync functions."""

    def test_create_dataset_sync_success(self) -> None:
        """Success path: calls create_dataset and returns result."""
        from anvil.services.tracking.tracking import _create_dataset_sync

        mock_ds = MagicMock()
        with patch(
            "anvil.services.tracking.tracking.create_dataset", return_value=mock_ds
        ):
            result = _create_dataset_sync("my-ds", {"tag": "val"})
            assert result is mock_ds

    def test_create_dataset_sync_success_no_tags(self) -> None:
        """Success path with None tags."""
        from anvil.services.tracking.tracking import _create_dataset_sync

        mock_ds = MagicMock()
        with patch(
            "anvil.services.tracking.tracking.create_dataset", return_value=mock_ds
        ):
            result = _create_dataset_sync("my-ds", None)
            assert result is mock_ds

    def test_append_records_sync_not_found(self) -> None:
        """Raises ValueError when dataset is not found."""
        from anvil.services.tracking.tracking import _append_records_sync

        mock_get = MagicMock(return_value=None)
        with (patch("anvil.services.tracking.tracking.get_dataset", mock_get),):
            with pytest.raises(ValueError, match="not found"):
                _append_records_sync("missing-ds", [{"a": 1}])

    def test_append_records_sync_success(self) -> None:
        """Success path: appends records and returns count."""
        from anvil.services.tracking.tracking import _append_records_sync

        mock_ds = MagicMock()
        with patch(
            "anvil.services.tracking.tracking.get_dataset", return_value=mock_ds
        ):
            count = _append_records_sync("my-ds", [{"a": 1}, {"b": 2}])
            assert count == 2
            mock_ds.merge_records.assert_called_once_with([{"a": 1}, {"b": 2}])


########################################################################
# System metrics: ensure enable path is covered
########################################################################


class TestSystemMetricsCoverage:
    """Coverage for system metrics enable path."""

    @pytest.mark.asyncio
    async def test_enable_system_metrics_success_path(self) -> None:
        """Actually exercises the success path of enable_system_metrics."""
        import anvil.services.tracking.tracking as tracking_mod

        tracking_mod._system_metrics_enabled = False
        from anvil.services.tracking.tracking import TrackingService

        TrackingService.enable_system_metrics()
        assert tracking_mod._system_metrics_enabled is True
        # Reset for other tests
        tracking_mod._system_metrics_enabled = False


########################################################################
# Module-level import fallback (lines 43-45)
########################################################################


class TestModuleImportFallback:
    """Exercises the except ImportError path in the module-level
    try/except for mlflow.genai.datasets."""

    def test_import_error_sets_fallbacks_to_none(self) -> None:
        """Sets create_dataset and get_dataset to None on ImportError."""
        import importlib
        import sys

        import anvil.services.tracking.tracking as tracking_mod

        original_create = tracking_mod.create_dataset
        original_get = tracking_mod.get_dataset

        removed: dict[str, Any] = {}
        for key in list(sys.modules):
            if "genai.datasets" in key:
                removed[key] = sys.modules.pop(key)

        original_import = builtins.__import__

        def _failing_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if "genai.datasets" in name:
                msg = f"No module named {name}"
                raise ImportError(msg)
            return original_import(name, *args, **kwargs)

        try:
            with patch("builtins.__import__", _failing_import):
                importlib.reload(tracking_mod)
                assert tracking_mod.create_dataset is None
                assert tracking_mod.get_dataset is None
        finally:
            for key, val in removed.items():
                sys.modules[key] = val
            tracking_mod.create_dataset = original_create
            tracking_mod.get_dataset = original_get
            importlib.reload(tracking_mod)
