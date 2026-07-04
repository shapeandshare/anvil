"""Tests for merge_service — utilities and AdapterMergeService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.services.training.merge_service import (
    AdapterMergeService,
    _safe_path_component,
)


class TestSafePathComponent:
    """Tests for _safe_path_component — path sanitisation."""

    def test_allows_alphanumeric(self) -> None:
        assert _safe_path_component("hello123") == "hello123"

    def test_allows_dot_dash_underscore(self) -> None:
        assert _safe_path_component("my.adapter-v1_final") == "my.adapter-v1_final"

    def test_replaces_special_chars_with_underscore(self) -> None:
        result = _safe_path_component("my adapter/name@#$%")
        assert "/" not in result
        assert "@" not in result
        assert result == "my_adapter_name____"

    def test_strips_whitespace_to_underscore(self) -> None:
        assert _safe_path_component("hello world") == "hello_world"

    def test_truncates_to_default_max_len(self) -> None:
        long_name = "a" * 200
        result = _safe_path_component(long_name)
        assert len(result) == 128

    def test_truncates_to_custom_max_len(self) -> None:
        result = _safe_path_component("hello world", max_len=5)
        assert result == "hello"

    def test_raises_on_empty_result(self) -> None:
        with pytest.raises(ValueError, match="empty after sanitisation"):
            _safe_path_component("")

    def test_special_chars_become_underscores(self) -> None:
        result = _safe_path_component("!!!@@@###")
        assert "!" not in result
        assert "@" not in result


###############################################################################
# Tests for AdapterMergeService
###############################################################################


class TestAdapterMergeService:
    """AdapterMergeService — merge, merge_and_export, helpers."""

    @pytest.fixture
    def svc(self):
        repo = MagicMock()
        store = MagicMock()
        tracking = MagicMock()
        ext_repo = MagicMock()
        return AdapterMergeService(
            lora_adapter_repo=repo,
            store=store,
            tracking=tracking,
            external_model_repo=ext_repo,
        )

    # ── merge() ────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_merge_adapter_not_found(self, svc):
        svc._repo.get_by_adapter_id = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found"):
            await svc.merge(model_id=1, adapter_id="nonexistent")

    @pytest.mark.asyncio
    async def test_merge_missing_deps(self, svc):
        mock_adapter = MagicMock()
        mock_adapter.storage_path = "/tmp/adapter"
        svc._repo.get_by_adapter_id = AsyncMock(return_value=mock_adapter)
        svc._resolve_source_identifier = AsyncMock(return_value="org/model")

        with patch(
            "anvil.services.training.merge_service._MERGE_DEPS_AVAILABLE",
            False,
        ):
            with pytest.raises(RuntimeError, match="peft, torch, and transformers"):
                await svc.merge(model_id=1, adapter_id="adapter-1")

    @pytest.mark.asyncio
    async def test_merge_success(self, svc):
        mock_adapter = MagicMock()
        mock_adapter.storage_path = "/tmp/adapter"
        svc._repo.get_by_adapter_id = AsyncMock(return_value=mock_adapter)
        svc._resolve_source_identifier = AsyncMock(return_value="org/model")

        mock_base_model = MagicMock()
        mock_adapter_model = MagicMock()
        mock_merged = MagicMock()

        with (
            patch(
                "anvil.services.training.merge_service._MERGE_DEPS_AVAILABLE",
                True,
            ),
            patch(
                "anvil.services.training.merge_service.AutoModelForCausalLM.from_pretrained",
                return_value=mock_base_model,
            ),
            patch(
                "anvil.services.training.merge_service.PeftModel.from_pretrained",
                return_value=mock_adapter_model,
            ),
        ):
            mock_adapter_model.merge_and_unload.return_value = mock_merged
            result = await svc.merge(model_id=1, adapter_id="adapter-1")
            assert result is not None
            assert "merged" in result

    # ── merge_and_export() ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_merge_and_export_adapter_not_found(self, svc):
        svc._repo.get_by_adapter_id = AsyncMock(return_value=None)
        result = await svc.merge_and_export(model_id=1, adapter_id="nonexistent")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_merge_and_export_already_merged(self, svc):
        mock_adapter = MagicMock()
        mock_adapter.merged_at = "2024-01-01T00:00:00Z"
        svc._repo.get_by_adapter_id = AsyncMock(return_value=mock_adapter)
        result = await svc.merge_and_export(model_id=1, adapter_id="adapter-1")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_merge_and_export_license_blocked(self, svc):
        mock_adapter = MagicMock()
        mock_adapter.merged_at = None
        svc._repo.get_by_adapter_id = AsyncMock(return_value=mock_adapter)
        svc._check_license = AsyncMock(return_value=(False, "License restricted"))
        result = await svc.merge_and_export(model_id=1, adapter_id="adapter-1")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_merge_and_export_missing_deps(self, svc):
        mock_adapter = MagicMock()
        mock_adapter.merged_at = None
        svc._repo.get_by_adapter_id = AsyncMock(return_value=mock_adapter)
        svc._check_license = AsyncMock(return_value=(True, ""))

        with patch(
            "anvil.services.training.merge_service._MERGE_DEPS_AVAILABLE",
            False,
        ):
            result = await svc.merge_and_export(model_id=1, adapter_id="adapter-1")
            assert "error" in result

    @pytest.mark.asyncio
    async def test_merge_and_export_source_identifier_fails(self, svc):
        mock_adapter = MagicMock()
        mock_adapter.merged_at = None
        svc._repo.get_by_adapter_id = AsyncMock(return_value=mock_adapter)
        svc._check_license = AsyncMock(return_value=(True, ""))
        svc._resolve_source_identifier = AsyncMock(
            side_effect=RuntimeError("Model not found")
        )

        with patch(
            "anvil.services.training.merge_service._MERGE_DEPS_AVAILABLE",
            True,
        ):
            result = await svc.merge_and_export(model_id=1, adapter_id="adapter-1")
            assert "error" in result

    # ── _resolve_source_identifier() ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_resolve_source_no_external_repo(self):
        svc = AdapterMergeService(
            lora_adapter_repo=MagicMock(),
            store=MagicMock(),
            tracking=MagicMock(),
            external_model_repo=None,
        )
        with pytest.raises(RuntimeError, match="no ExternalModelRepository"):
            await svc._resolve_source_identifier(model_id=1)

    @pytest.mark.asyncio
    async def test_resolve_source_model_not_found(self, svc):
        svc._external_model_repo.get = AsyncMock(return_value=None)
        with pytest.raises(RuntimeError, match="not found"):
            await svc._resolve_source_identifier(model_id=999)

    @pytest.mark.asyncio
    async def test_resolve_source_local_assets(self, svc):
        mock_model = MagicMock()
        mock_model.asset_availability = "assets_available"
        mock_model.runnable_status = "runnable"
        mock_model.source_identifier = "org/model"
        svc._external_model_repo.get = AsyncMock(return_value=mock_model)

        with patch(
            "anvil.services.training.merge_service.Path.exists",
            return_value=True,
        ):
            result = await svc._resolve_source_identifier(model_id=1)
            assert "data/storage/models/1/hf" in result

    @pytest.mark.asyncio
    async def test_resolve_source_fallback_to_hub(self, svc):
        mock_model = MagicMock()
        mock_model.asset_availability = "not_available"
        mock_model.runnable_status = "runnable"
        mock_model.source_identifier = "org/model"
        svc._external_model_repo.get = AsyncMock(return_value=mock_model)

        result = await svc._resolve_source_identifier(model_id=1)
        assert result == "org/model"

    # ── _check_license() ───────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_check_license_no_repo(self):
        svc = AdapterMergeService(
            lora_adapter_repo=MagicMock(),
            store=MagicMock(),
            tracking=MagicMock(),
            external_model_repo=None,
        )
        ok, msg = await svc._check_license(model_id=1)
        assert ok is True
        assert msg == ""

    @pytest.mark.asyncio
    async def test_check_license_model_not_found(self, svc):
        svc._external_model_repo.get = AsyncMock(return_value=None)
        ok, msg = await svc._check_license(model_id=999)
        assert ok is False
        assert "not found" in msg

    @pytest.mark.asyncio
    async def test_check_license_restricted(self, svc):
        mock_model = MagicMock()
        mock_model.license = "cc-by-nc-4.0"
        svc._external_model_repo.get = AsyncMock(return_value=mock_model)
        ok, msg = await svc._check_license(model_id=1)
        assert ok is False
        assert "restricts redistribution" in msg

    @pytest.mark.asyncio
    async def test_check_license_permissive(self, svc):
        mock_model = MagicMock()
        mock_model.license = "apache-2.0"
        svc._external_model_repo.get = AsyncMock(return_value=mock_model)
        ok, msg = await svc._check_license(model_id=1)
        assert ok is True
        assert msg == ""

    # ── _register_lineage() ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_register_lineage_no_tracking(self):
        svc = AdapterMergeService(
            lora_adapter_repo=MagicMock(),
            store=MagicMock(),
            tracking=None,
            external_model_repo=MagicMock(),
        )
        result = await svc._register_lineage(
            model_id=1,
            adapter_id="adapter-1",
            adapter_method="lora",
            export_dir="/tmp/export",
        )
        assert result["registered"] is False

    @pytest.mark.asyncio
    async def test_register_lineage_run_fails(self, svc):
        svc._tracking.start_run = AsyncMock(return_value="")
        result = await svc._register_lineage(
            model_id=1,
            adapter_id="adapter-1",
            adapter_method="lora",
            export_dir="/tmp/export",
        )
        assert result["registered"] is False
        assert "Failed to create MLflow run" in result["error"]

    @pytest.mark.asyncio
    async def test_register_lineage_success(self, svc):
        svc._tracking.start_run = AsyncMock(return_value="run_123")
        svc._tracking.log_artifact_dir = AsyncMock()
        svc._tracking.register_source_model = AsyncMock(
            return_value={"name": "model", "version": "1"}
        )
        svc._tracking.set_tag = AsyncMock()
        svc._tracking.finish_run = AsyncMock()

        result = await svc._register_lineage(
            model_id=1,
            adapter_id="adapter-1",
            adapter_method="lora",
            export_dir="/tmp/export",
        )
        assert result["registered"] is True
        assert result["registry_name"] == "model"
        assert result["run_id"] == "run_123"

    # ── _merge_hf_weights() ────────────────────────────────────────────

    def test_merge_hf_weights_success(self):
        mock_adapter = MagicMock()
        mock_adapter.storage_path = "/tmp/adapter"

        mock_base = MagicMock()
        mock_adapter_model = MagicMock()
        mock_merged = MagicMock()

        with (
            patch(
                "anvil.services.training.merge_service.AutoModelForCausalLM.from_pretrained",
                return_value=mock_base,
            ),
            patch(
                "anvil.services.training.merge_service.PeftModel.from_pretrained",
                return_value=mock_adapter_model,
            ),
        ):
            mock_adapter_model.merge_and_unload.return_value = mock_merged
            result = AdapterMergeService._merge_hf_weights(
                "org/model", mock_adapter, 1, "adapter-1"
            )
            assert result is mock_merged

    def test_merge_hf_weights_os_error(self):
        mock_adapter = MagicMock()
        mock_adapter.storage_path = "/tmp/adapter"

        with patch(
            "anvil.services.training.merge_service.AutoModelForCausalLM.from_pretrained",
            side_effect=OSError("File not found"),
        ):
            result = AdapterMergeService._merge_hf_weights(
                "org/model", mock_adapter, 1, "adapter-1"
            )
            assert isinstance(result, dict)
            assert "error" in result

    # ── _publish_artifact() ────────────────────────────────────────────

    def test_publish_artifact_success(self):
        mock_merged = MagicMock()
        mock_merged.save_pretrained = MagicMock()

        with (
            patch(
                "anvil.services.training.merge_service.AutoTokenizer.from_pretrained",
            ) as mock_tokenizer,
            patch(
                "anvil.services.training.merge_service.Path.exists",
                return_value=False,
            ),
            patch(
                "anvil.services.training.merge_service.Path.mkdir",
            ),
            patch(
                "anvil.services.training.merge_service.os.replace",
            ),
        ):
            mock_tokenizer.return_value.save_pretrained = MagicMock()
            result = AdapterMergeService._publish_artifact(
                mock_merged, "org/model", 1, "adapter-1"
            )
            assert "data/storage/models/1/merged/adapter-1" in str(result)

    def test_publish_artifact_os_error(self):
        mock_merged = MagicMock()
        mock_merged.save_pretrained = MagicMock()

        with (
            patch(
                "anvil.services.training.merge_service.AutoTokenizer.from_pretrained",
            ),
            patch(
                "anvil.services.training.merge_service.Path.mkdir",
            ),
            patch(
                "anvil.services.training.merge_service.os.replace",
                side_effect=OSError("Permission denied"),
            ),
        ):
            result = AdapterMergeService._publish_artifact(
                mock_merged, "org/model", 1, "adapter-1"
            )
            assert isinstance(result, dict)
            assert "error" in result


class TestRestrictedLicenses:
    """Direct check of restricted license set membership."""

    def test_known_restricted_licenses(self):
        from anvil.services.training.merge_service import _RESTRICTED_LICENSES

        assert "cc-by-nc-4.0" in _RESTRICTED_LICENSES
        assert "cc-by-nc-sa-4.0" in _RESTRICTED_LICENSES
        assert "odbl" in _RESTRICTED_LICENSES
        assert "unknown" in _RESTRICTED_LICENSES
        assert "apache-2.0" not in _RESTRICTED_LICENSES
        assert "mit" not in _RESTRICTED_LICENSES
