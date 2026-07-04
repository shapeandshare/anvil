"""Unit tests for ModelCatalogService register_external_model.

This test suite validates the import-run registration pattern (D1):
register_external_model MUST create a lightweight MLflow run, log the
config manifest as an artifact, and use ``runs:/{run_id}/config.json``
as the ``create_model_version`` source with a valid ``run_id``.

Local filesystem sources without a ``run_id`` are rejected by the MLflow
server (CVE-2023-6014/6015/6018/6831 — verified in MLflow 3.x source).
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from anvil.services._shared.asset_state import AssetState
from anvil.services._shared.runnable_status import RunnableStatus
from anvil.services.catalog.catalog_kind import CatalogKind
from anvil.services.catalog.lifecycle_state import LifecycleState
from anvil.services.catalog.model_catalog_service import (
    CatalogUnavailableError,
    ModelCatalogService,
)


class TestRegisterExternalModel:
    """Tests for ModelCatalogService.register_external_model()."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Return a pre-configured mock MlflowClient."""
        client = MagicMock()

        # create_run → Run-like object with .info.run_id
        mock_run = MagicMock()
        mock_run.info.run_id = "test-run-id-123"
        client.create_run.return_value = mock_run

        # create_model_version → Version-like object with .version
        mock_version = MagicMock()
        mock_version.version = "1"
        client.create_model_version.return_value = mock_version

        return client

    @pytest.fixture
    async def service(self, mock_client: MagicMock) -> ModelCatalogService:
        """Return a ModelCatalogService with a pre-set mock client."""
        svc = ModelCatalogService(tracking_uri="http://mock:5000")
        svc._client = mock_client
        return svc

    @pytest.mark.asyncio
    async def test_creates_import_run_and_uses_runs_uri(
        self, service: ModelCatalogService, mock_client: MagicMock
    ) -> None:
        """register_external_model creates an import run and uses runs:/ URI."""
        result = await service.register_external_model(
            catalog_name="hf--test-model",
            display_name="test/model",
            source_type="huggingface",
            source_identifier="test/model",
            revision_sha="abc123",
            architecture_family="LlamaForCausalLM",
            tokenizer_family="sentencepiece",
            license="mit",
            parameter_count=1000,
            runnable_status=RunnableStatus.RUNNABLE,
            runnable_reason=None,
            config_json='{"key": "value"}',
        )

        # ── Assert create_run was called ──────────────────────────────
        mock_client.create_run.assert_called_once()
        # The experiment_id is passed as a keyword argument
        create_run_kwargs = mock_client.create_run.call_args[1]
        assert create_run_kwargs.get("experiment_id") == "0"

        # ── Assert log_artifact was called ─────────────────────────────
        mock_client.log_artifact.assert_called_once()
        log_args = mock_client.log_artifact.call_args[0]
        assert log_args[0] == "test-run-id-123"  # run_id
        # The temp file path should end with .json (file is cleaned up
        # by the implementation after logging, so we verify existence
        # and content via captured data from the mock).
        assert log_args[1].endswith(".json")

        # ── Assert create_model_version was called with runs:/ URI ────
        mock_client.create_model_version.assert_called_once()
        mv_kwargs = mock_client.create_model_version.call_args[1]
        assert mv_kwargs["name"] == "hf--test-model"
        assert mv_kwargs["source"] == "runs:/test-run-id-123/config.json"
        assert mv_kwargs["run_id"] == "test-run-id-123"

        # ── Assert tags are set ───────────────────────────────────────
        tags = mv_kwargs.get("tags", {})
        assert tags.get("anvil.kind") == str(CatalogKind.EXTERNAL)
        assert tags.get("anvil.source_type") == "huggingface"
        assert tags.get("anvil.source_identifier") == "test/model"
        assert tags.get("anvil.revision_sha") == "abc123"

        # ── Assert result ─────────────────────────────────────────────
        assert result.name == "hf--test-model"
        assert result.version == 1

    @pytest.mark.asyncio
    async def test_default_experiment_import_run(
        self, service: ModelCatalogService, mock_client: MagicMock
    ) -> None:
        """The import run uses the MLflow Default experiment (ID '0')."""
        await service.register_external_model(
            catalog_name="hf--test-model",
            display_name="test/model",
            source_type="huggingface",
            source_identifier="test/model",
            revision_sha="abc123",
            architecture_family="LlamaForCausalLM",
            tokenizer_family="sentencepiece",
            license="mit",
            parameter_count=1000,
            runnable_status=RunnableStatus.RUNNABLE,
            runnable_reason=None,
            config_json="{}",
        )

        mock_client.create_run.assert_called_once()
        args, kwargs = mock_client.create_run.call_args
        assert kwargs.get("experiment_id") == "0"

    @pytest.mark.asyncio
    async def test_no_config_json_skips_artifact(
        self, service: ModelCatalogService, mock_client: MagicMock
    ) -> None:
        """When config_json is None, no artifact is logged but run is still created."""
        await service.register_external_model(
            catalog_name="hf--no-config",
            display_name="no config",
            source_type="huggingface",
            source_identifier="no/config",
            revision_sha="abc",
            architecture_family="LlamaForCausalLM",
            tokenizer_family="sentencepiece",
            license="mit",
            parameter_count=100,
            runnable_status=RunnableStatus.TRACK_ONLY,
            runnable_reason=None,
            config_json=None,
        )

        # Run should be created
        mock_client.create_run.assert_called_once()
        # No artifact logged
        mock_client.log_artifact.assert_not_called()
        # Model version should still be created
        mock_client.create_model_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_transient_failure_raises_catalog_unavailable(
        self, mock_client: MagicMock
    ) -> None:
        """If MLflow raises a transient exception, CatalogUnavailableError is raised."""
        mock_client.create_run.side_effect = ConnectionError("MLflow is down")

        service = ModelCatalogService(tracking_uri="http://mock:5000")
        service._client = mock_client

        with pytest.raises(CatalogUnavailableError) as excinfo:
            await service.register_external_model(
                catalog_name="hf--fail",
                display_name="fail",
                source_type="huggingface",
                source_identifier="fail",
                revision_sha="abc",
                architecture_family="LlamaForCausalLM",
                tokenizer_family="sentencepiece",
                license="mit",
                parameter_count=100,
                runnable_status=RunnableStatus.TRACK_ONLY,
                runnable_reason=None,
                config_json="{}",
            )

        # Verify the exception is raised with the right wrapping
        assert "MLflow is down" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_tags_include_asset_availability_metadata_only(
        self, service: ModelCatalogService, mock_client: MagicMock
    ) -> None:
        """Tags include METADATA_ONLY asset availability for imported models."""
        await service.register_external_model(
            catalog_name="hf--tag-test",
            display_name="tag test",
            source_type="huggingface",
            source_identifier="tag/test",
            revision_sha="def456",
            architecture_family="LlamaForCausalLM",
            tokenizer_family="sentencepiece",
            license="apache-2.0",
            parameter_count=500,
            runnable_status=RunnableStatus.RUNNABLE,
            runnable_reason=None,
            config_json="{}",
        )

        mv_kwargs = mock_client.create_model_version.call_args[1]
        tags = mv_kwargs.get("tags", {})
        assert tags.get("anvil.asset_availability") == str(AssetState.METADATA_ONLY)
        assert tags.get("anvil.lifecycle_state") == str(LifecycleState.ACTIVE)
        assert tags.get("anvil.parameter_count") == "500"
        assert tags.get("anvil.license") == "apache-2.0"
        assert "anvil.created_at" in tags

    @pytest.mark.asyncio
    async def test_temp_file_cleaned_up_after_log(
        self, service: ModelCatalogService, mock_client: MagicMock
    ) -> None:
        """The temp config file is removed after logging to MLflow."""
        # Capture the temp file path from log_artifact
        captured_path: list[str] = []

        def _capture_path(run_id: str, local_path: str, **kwargs: object) -> None:
            captured_path.append(local_path)

        mock_client.log_artifact.side_effect = _capture_path

        await service.register_external_model(
            catalog_name="hf--cleanup",
            display_name="cleanup test",
            source_type="huggingface",
            source_identifier="cleanup/test",
            revision_sha="ghi789",
            architecture_family="LlamaForCausalLM",
            tokenizer_family="sentencepiece",
            license="mit",
            parameter_count=100,
            runnable_status=RunnableStatus.TRACK_ONLY,
            runnable_reason=None,
            config_json='{"cleanup": true}',
        )

        # Verify temp file was removed after the call
        assert len(captured_path) == 1
        assert not os.path.isfile(captured_path[0])
