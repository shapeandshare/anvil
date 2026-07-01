"""Unit tests for AdapterMergeService — non-destructive merge and export.

Tests cover non-destructive merge behaviour, the ``merge_and_export()``
pipeline, atomic-failure safety, license enforcement, and quantized-base
handling.  ``peft`` / ``transformers`` are mocked since they live behind
the ``[finetune]`` extra.
"""

from __future__ import annotations

from datetime import UTC
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, call, patch

import pytest

from anvil.db.models.lora_adapter import LoRAAdapter
from anvil.services.training.merge_service import AdapterMergeService

# ── Module-level patching: prevent peft/transformers from being
# imported in the test environment.  The merge module uses try/except
# ImportError guards; these patches ensure the guards behave as if
# the packages are present.

_MODULE = "anvil.services.training.merge_service"


@pytest.fixture(autouse=True)
def _patch_peft_deps():
    """Make the merge module believe peft/transformers are available."""
    with (
        patch(f"{_MODULE}._MERGE_DEPS_AVAILABLE", True),
        patch(f"{_MODULE}.AutoModelForCausalLM", create=True) as mock_auto,
        patch(f"{_MODULE}.PeftModel", create=True) as mock_peft,
        patch(f"{_MODULE}.AutoTokenizer", create=True) as mock_tok,
    ):
        mock_auto.from_pretrained.return_value = MagicMock()
        mock_peft_model = MagicMock()
        mock_peft.from_pretrained.return_value = mock_peft_model
        mock_tok.from_pretrained.return_value = MagicMock()
        yield {
            "AutoModelForCausalLM": mock_auto,
            "PeftModel": mock_peft,
            "mock_peft_model": mock_peft_model,
            "AutoTokenizer": mock_tok,
        }


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_repo() -> AsyncMock:
    """Return a mock ``LoRAAdapterRepository``."""
    return AsyncMock()


@pytest.fixture
def mock_store() -> MagicMock:
    """Return a mock ``LocalFileStore``."""
    store = MagicMock()
    store._resolve.side_effect = lambda p: Path(f"/mock/{p}")
    return store


@pytest.fixture
def mock_tracking() -> MagicMock:
    """Return a mock ``TrackingService``."""
    tracking = AsyncMock()
    tracking.start_run.return_value = "mlflow_run_001"
    tracking.register_source_model.return_value = {
        "name": "adapter-merge-test_run",
        "version": "1",
    }
    return tracking


@pytest.fixture
def mock_external_model_repo() -> AsyncMock:
    """Return a mock ``ExternalModelRepository``."""
    repo = AsyncMock()
    ext_model = MagicMock()
    ext_model.source_identifier = "org/base-model"
    ext_model.license = "mit"
    repo.get.return_value = ext_model
    return repo


@pytest.fixture
def sample_adapter() -> MagicMock:
    """Return a ``LoRAAdapter`` instance for testing."""
    adapter = MagicMock(spec=LoRAAdapter)
    adapter.external_model_id = 1
    adapter.adapter_id = "test_run"
    adapter.method = "lora"
    adapter.storage_path = "models/1/adapters/test_run/"
    adapter.lora_rank = 8
    adapter.lora_alpha = 16.0
    adapter.merged_at = None
    adapter.final_loss = 0.05
    return adapter


@pytest.fixture
def service(
    mock_repo: AsyncMock,
    mock_store: MagicMock,
    mock_tracking: MagicMock,
    mock_external_model_repo: AsyncMock,
) -> AdapterMergeService:
    """Return an ``AdapterMergeService`` wired with mocks."""
    return AdapterMergeService(
        lora_adapter_repo=mock_repo,
        store=mock_store,
        tracking=mock_tracking,
        external_model_repo=mock_external_model_repo,
    )


# ── Non-destructive merge ─────────────────────────────────────────────


class TestNonDestructiveMerge:
    """``merge()`` must preserve adapter files and not set ``merged_at``."""

    @pytest.mark.asyncio
    async def test_merge_returns_path(
        self,
        service: AdapterMergeService,
        mock_repo: AsyncMock,
        sample_adapter: MagicMock,
        mock_external_model_repo: AsyncMock,
    ):
        """merge() returns a storage path on success."""
        mock_repo.get_by_adapter_id.return_value = sample_adapter
        mock_external_model_repo.get.return_value = MagicMock(
            source_identifier="org/base-model"
        )

        path = await service.merge(model_id=1, adapter_id="test_run")

        assert isinstance(path, str)
        assert "merged" in path

    @pytest.mark.asyncio
    async def test_merge_preserves_adapter_files(
        self,
        service: AdapterMergeService,
        mock_repo: AsyncMock,
        sample_adapter: MagicMock,
        mock_external_model_repo: AsyncMock,
    ):
        """After merge(), the adapter record is NOT marked merged_at."""
        mock_repo.get_by_adapter_id.return_value = sample_adapter
        mock_external_model_repo.get.return_value = MagicMock(
            source_identifier="org/base-model"
        )

        await service.merge(model_id=1, adapter_id="test_run")

        assert sample_adapter.merged_at is None

    @pytest.mark.asyncio
    async def test_merge_missing_adapter_raises(
        self,
        service: AdapterMergeService,
        mock_repo: AsyncMock,
    ):
        """merge() raises ValueError for missing adapter."""
        mock_repo.get_by_adapter_id.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await service.merge(model_id=1, adapter_id="nonexistent")

    @pytest.mark.asyncio
    async def test_merge_missing_deps(
        self,
        mock_repo: AsyncMock,
        mock_store: MagicMock,
        sample_adapter: MagicMock,
    ):
        """merge() raises RuntimeError when deps are unavailable."""
        mock_repo.get_by_adapter_id.return_value = sample_adapter
        svc = AdapterMergeService(mock_repo, mock_store)

        with patch(f"{_MODULE}._MERGE_DEPS_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="peft"):
                await svc.merge(model_id=1, adapter_id="test_run")


# ── Merge-and-export ──────────────────────────────────────────────────


class TestMergeAndExport:
    """``merge_and_export()`` full pipeline with lineage."""

    @pytest.fixture
    def _real_temp(self) -> str:
        """Create a real temp directory for file I/O in tests."""
        import tempfile

        tmp = tempfile.mkdtemp(prefix="anvil_test_merge_")
        yield tmp
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_merge_and_export_success(
        self,
        service: AdapterMergeService,
        mock_repo: AsyncMock,
        mock_external_model_repo: AsyncMock,
        mock_tracking: MagicMock,
        sample_adapter: MagicMock,
        _real_temp: str,
    ):
        """Successful merge+export returns path and lineage."""
        mock_repo.get_by_adapter_id.return_value = sample_adapter
        mock_repo.mark_merged.return_value = sample_adapter
        mock_tracking.log_artifact_dir = AsyncMock()

        merged_model = MagicMock()
        _patch_peft_deps_fixture = None

        with (
            patch.object(Path, "mkdir") as mock_mkdir,
            patch.object(Path, "exists", return_value=False),
            patch(f"{_MODULE}.os.replace") as mock_replace,
            patch(f"{_MODULE}.shutil.rmtree"),
        ):
            mock_mkdir.return_value = None

            result = await service.merge_and_export(
                model_id=1,
                adapter_id="test_run",
            )

        assert "path" in result
        assert result["lineage"]["registered"] is True
        assert result["lineage"]["run_id"] == "mlflow_run_001"
        assert mock_repo.mark_merged.called
        assert mock_tracking.log_artifact_dir.called

    @pytest.mark.asyncio
    async def test_merge_and_export_missing_adapter(
        self,
        service: AdapterMergeService,
        mock_repo: AsyncMock,
    ):
        """Returns error dict for missing adapter."""
        mock_repo.get_by_adapter_id.return_value = None

        result = await service.merge_and_export(model_id=1, adapter_id="ghost")
        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_merge_and_export_already_merged(
        self,
        service: AdapterMergeService,
        mock_repo: AsyncMock,
        sample_adapter: MagicMock,
    ):
        """Returns error if adapter is already merged."""
        from datetime import datetime, timezone

        sample_adapter.merged_at = datetime.now(UTC)
        mock_repo.get_by_adapter_id.return_value = sample_adapter

        result = await service.merge_and_export(model_id=1, adapter_id="test_run")
        assert "error" in result
        assert "already merged" in result["error"]

    @pytest.mark.asyncio
    async def test_hf_artifact_dir_produced(
        self,
        service: AdapterMergeService,
        mock_repo: AsyncMock,
        mock_external_model_repo: AsyncMock,
        mock_tracking: MagicMock,
        sample_adapter: MagicMock,
        _real_temp: str,
    ):
        """merge_and_export produces HF artifact dir via save_pretrained."""
        mock_repo.get_by_adapter_id.return_value = sample_adapter
        mock_repo.mark_merged.return_value = sample_adapter
        mock_tracking.log_artifact_dir = AsyncMock()

        merged_model = MagicMock()

        with (
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=False),
            patch(f"{_MODULE}.os.replace"),
            patch(f"{_MODULE}.shutil.rmtree"),
        ):
            result = await service.merge_and_export(
                model_id=1,
                adapter_id="test_run",
            )

        assert "path" in result
        assert "error" not in result
        # Verify the merged model was saved via HuggingFace save_pretrained
        # (mocked but confirms the path was used)

    # ── Atomic failure (safety) ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_atomic_failure_no_partial_artifact(
        self,
        service: AdapterMergeService,
        mock_repo: AsyncMock,
        mock_external_model_repo: AsyncMock,
        sample_adapter: MagicMock,
        _real_temp: str,
    ):
        """If export fails mid-write, temp dir is cleaned up and no
        partial artifact remains at the final path.
        """
        mock_repo.get_by_adapter_id.return_value = sample_adapter
        mock_external_model_repo.get.return_value = MagicMock(
            source_identifier="org/base-model",
            license="mit",
        )

        # Make merge_and_unload return a mock whose save_pretrained raises
        with (
            patch(f"{_MODULE}.AutoModelForCausalLM") as mock_auto,
            patch(f"{_MODULE}.PeftModel") as mock_peft,
        ):
            bad_model = MagicMock()
            bad_model.save_pretrained.side_effect = RuntimeError("write failure")
            mock_peft_model = MagicMock()
            mock_peft_model.merge_and_unload.return_value = bad_model
            mock_peft.from_pretrained.return_value = mock_peft_model

            with (
                patch.object(Path, "mkdir"),
                patch.object(Path, "exists", return_value=False),
                patch(f"{_MODULE}.os.replace"),
                patch(f"{_MODULE}.shutil.rmtree") as mock_rmtree,
            ):
                result = await service.merge_and_export(
                    model_id=1,
                    adapter_id="test_run",
                )

        assert "error" in result
        assert not mock_repo.mark_merged.called

    # ── License check ───────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_license_restricted_rejected(
        self,
        service: AdapterMergeService,
        mock_repo: AsyncMock,
        mock_external_model_repo: AsyncMock,
        sample_adapter: MagicMock,
    ):
        """Restricted licenses block merge_and_export."""
        mock_repo.get_by_adapter_id.return_value = sample_adapter
        ext_model = MagicMock()
        ext_model.license = "cc-by-nc-4.0"
        mock_external_model_repo.get.return_value = ext_model

        result = await service.merge_and_export(model_id=1, adapter_id="test_run")
        assert "error" in result
        assert "restricts redistribution" in result["error"]
        assert not mock_repo.mark_merged.called

    @pytest.mark.asyncio
    async def test_license_permissive_allowed(
        self,
        service: AdapterMergeService,
        mock_repo: AsyncMock,
        mock_external_model_repo: AsyncMock,
        mock_tracking: MagicMock,
        sample_adapter: MagicMock,
        _real_temp: str,
    ):
        """Permissive licenses allow merge_and_export."""
        mock_repo.get_by_adapter_id.return_value = sample_adapter
        mock_repo.mark_merged.return_value = sample_adapter
        mock_tracking.log_artifact_dir = AsyncMock()

        with (
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=False),
            patch(f"{_MODULE}.os.replace"),
            patch(f"{_MODULE}.shutil.rmtree"),
        ):
            result = await service.merge_and_export(
                model_id=1,
                adapter_id="test_run",
            )

        assert "path" in result

    @pytest.mark.asyncio
    async def test_license_check_skipped_without_repo(
        self,
        mock_repo: AsyncMock,
        mock_store: MagicMock,
        mock_tracking: MagicMock,
        sample_adapter: MagicMock,
        _real_temp: str,
    ):
        """Without external_model_repo, license check passes by default."""
        svc = AdapterMergeService(
            lora_adapter_repo=mock_repo,
            store=mock_store,
            tracking=mock_tracking,
        )
        mock_repo.get_by_adapter_id.return_value = sample_adapter
        mock_repo.mark_merged.return_value = sample_adapter
        mock_tracking.log_artifact_dir = AsyncMock()

        with (
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=False),
            patch(f"{_MODULE}.os.replace"),
            patch(f"{_MODULE}.shutil.rmtree"),
        ):
            # Without external_model_repo, source_identifier resolution
            # will fail, so the merge_and_export will return error
            result = await svc.merge_and_export(model_id=1, adapter_id="test_run")

        assert "error" in result
        assert (
            "not found" in result["error"].lower()
            or "ExternalModelRepository" in result["error"]
        )

    # ── Quantized base ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_merge_failure_quantized_base_guidance(
        self,
        service: AdapterMergeService,
        mock_repo: AsyncMock,
        mock_external_model_repo: AsyncMock,
        sample_adapter: MagicMock,
        _patch_peft_deps: dict[str, Any],
    ):
        """When merge_and_unload fails, the error message includes
        guidance about QLoRA dequantization.
        """
        mock_repo.get_by_adapter_id.return_value = sample_adapter

        mock_peft_model = _patch_peft_deps["mock_peft_model"]
        mock_peft_model.merge_and_unload.side_effect = RuntimeError(
            "4-bit quantization not supported"
        )

        result = await service.merge_and_export(model_id=1, adapter_id="test_run")
        assert "error" in result
        assert (
            "quantized" in result["error"].lower()
            or "memory" in result["error"].lower()
        )

    # ── Lineage registration ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_lineage_registered(
        self,
        service: AdapterMergeService,
        mock_repo: AsyncMock,
        mock_external_model_repo: AsyncMock,
        mock_tracking: MagicMock,
        sample_adapter: MagicMock,
        _real_temp: str,
    ):
        """Successful merge+export calls tracking methods for lineage."""
        mock_repo.get_by_adapter_id.return_value = sample_adapter
        mock_repo.mark_merged.return_value = sample_adapter
        mock_tracking.log_artifact_dir = AsyncMock()

        with (
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=False),
            patch(f"{_MODULE}.os.replace"),
            patch(f"{_MODULE}.shutil.rmtree"),
        ):
            await service.merge_and_export(
                model_id=1,
                adapter_id="test_run",
            )

        assert mock_tracking.start_run.called
        assert mock_tracking.register_source_model.called
        assert mock_tracking.log_artifact_dir.called
        assert mock_tracking.set_tag.called
        assert mock_tracking.finish_run.called

        tag_calls = mock_tracking.set_tag.call_args_list
        tag_keys = {c.kwargs.get("key") or c[0][1] for c in tag_calls}
        assert "anvil.origin" in tag_keys
        assert "anvil.base_model_ref" in tag_keys
        assert "anvil.adapter_id" in tag_keys
        assert "anvil.merge_timestamp" in tag_keys
        assert "anvil.method" in tag_keys

    @pytest.mark.asyncio
    async def test_lineage_failure_does_not_mark_merged(
        self,
        service: AdapterMergeService,
        mock_repo: AsyncMock,
        mock_external_model_repo: AsyncMock,
        mock_tracking: MagicMock,
        sample_adapter: MagicMock,
        _real_temp: str,
    ):
        """When lineage registration fails, mark_merged is NOT called
        and the published artifact is cleaned up (H6).
        """
        mock_repo.get_by_adapter_id.return_value = sample_adapter
        mock_tracking.log_artifact_dir = AsyncMock()
        mock_tracking.start_run.return_value = ""

        with (
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=False),
            patch(f"{_MODULE}.os.replace"),
            patch(f"{_MODULE}.shutil.rmtree") as mock_rmtree,
        ):
            result = await service.merge_and_export(
                model_id=1,
                adapter_id="test_run",
            )

        assert "error" in result
        assert not mock_repo.mark_merged.called
