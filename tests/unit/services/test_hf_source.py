# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for the HuggingFace Hub ModelSource.

Mocks ``_do_resolve`` and the availability probe so no network calls
and no ``huggingface_hub`` dependency are required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.services._shared.import_types import ModelMetadata, ModelSourceError
from anvil.services.model_import.hf_source import HfHubSource


@pytest.mark.asyncio
async def test_missing_extra_raises():
    """When huggingface_hub is unavailable, resolve raises missing_extra."""
    with patch(
        "anvil.services.model_import.hf_source._huggingface_hub_available",
        return_value=False,
    ):
        source = HfHubSource()
        with pytest.raises(ModelSourceError) as exc:
            await source.resolve_metadata("org/model")
        assert exc.value.code == "missing_extra"


@pytest.mark.asyncio
async def test_resolve_delegates_to_do_resolve():
    """When available, resolve_metadata returns _do_resolve's metadata."""
    fake_meta = ModelMetadata(
        display_name="org/model",
        architecture_family="LlamaForCausalLM",
        parameter_count=1_100_000_000,
        license="apache-2.0",
        tokenizer_family="LlamaTokenizer",
        revision_sha="deadbeef",
    )
    with (
        patch(
            "anvil.services.model_import.hf_source._huggingface_hub_available",
            return_value=True,
        ),
        patch(
            "anvil.services.model_import.hf_source._do_resolve",
            return_value=fake_meta,
        ) as mock_resolve,
    ):
        source = HfHubSource()
        meta = await source.resolve_metadata("org/model", revision="main")
        assert meta.architecture_family == "LlamaForCausalLM"
        assert meta.revision_sha == "deadbeef"
        mock_resolve.assert_awaited_once()


@pytest.mark.asyncio
async def test_token_falls_back_to_env(monkeypatch):
    """When no token is passed, HF_TOKEN env var is used."""
    monkeypatch.setenv("HF_TOKEN", "hf_secret")
    captured: dict[str, str | None] = {}

    async def _fake_resolve(identifier, revision, token):
        captured["token"] = token
        return ModelMetadata(
            display_name=identifier,
            architecture_family="LlamaForCausalLM",
            parameter_count=1,
            license="mit",
            tokenizer_family="x",
            revision_sha="s",
        )

    with (
        patch(
            "anvil.services.model_import.hf_source._huggingface_hub_available",
            return_value=True,
        ),
        patch(
            "anvil.services.model_import.hf_source._do_resolve",
            side_effect=_fake_resolve,
        ),
    ):
        source = HfHubSource()
        await source.resolve_metadata("org/model")
        assert captured["token"] == "hf_secret"


@pytest.mark.asyncio
async def test_explicit_token_overrides_env(monkeypatch):
    """An explicit token argument takes precedence over HF_TOKEN."""
    monkeypatch.setenv("HF_TOKEN", "env_token")
    captured: dict[str, str | None] = {}

    async def _fake_resolve(identifier, revision, token):
        captured["token"] = token
        return ModelMetadata(
            display_name=identifier,
            architecture_family="LlamaForCausalLM",
            parameter_count=1,
            license="mit",
            tokenizer_family="x",
            revision_sha="s",
        )

    with (
        patch(
            "anvil.services.model_import.hf_source._huggingface_hub_available",
            return_value=True,
        ),
        patch(
            "anvil.services.model_import.hf_source._do_resolve",
            side_effect=_fake_resolve,
        ),
    ):
        source = HfHubSource()
        await source.resolve_metadata("org/model", token="explicit_token")
        assert captured["token"] == "explicit_token"


###############################################################################
# Extended tests — list_asset_files, download_asset_to_path, _do_resolve errors
###############################################################################


@pytest.mark.asyncio
async def test_list_asset_files_missing_extra():
    """When huggingface_hub is unavailable, list_asset_files raises."""
    with patch(
        "anvil.services.model_import.hf_source._huggingface_hub_available",
        return_value=False,
    ):
        source = HfHubSource()
        with pytest.raises(ModelSourceError) as exc:
            await source.list_asset_files("org/model")
        assert exc.value.code == "missing_extra"


@pytest.mark.asyncio
async def test_list_asset_files_delegates():
    """list_asset_files returns categorized file list."""
    fake_assets = [
        {"asset_type": "config", "filename": "config.json"},
        {"asset_type": "tokenizer", "filename": "tokenizer.json"},
        {"asset_type": "weights", "filename": "model.safetensors"},
    ]

    async def _fake_list_files(identifier, revision, token):
        return fake_assets

    with (
        patch(
            "anvil.services.model_import.hf_source._huggingface_hub_available",
            return_value=True,
        ),
        patch(
            "anvil.services.model_import.hf_source._do_list_files",
            side_effect=_fake_list_files,
        ),
    ):
        source = HfHubSource()
        assets = await source.list_asset_files("org/model")
        assert len(assets) == 3
        assert assets[0]["asset_type"] == "config"
        assert assets[1]["asset_type"] == "tokenizer"
        assert assets[2]["asset_type"] == "weights"


@pytest.mark.asyncio
async def test_download_asset_missing_extra():
    """When huggingface_hub is unavailable, download_asset_to_path raises."""
    with patch(
        "anvil.services.model_import.hf_source._huggingface_hub_available",
        return_value=False,
    ):
        source = HfHubSource()
        with pytest.raises(ModelSourceError) as exc:
            await source.download_asset_to_path("org/model", "model.safetensors")
        assert exc.value.code == "missing_extra"


@pytest.mark.asyncio
async def test_download_asset_delegates():
    """download_asset_to_path returns a local path."""
    with (
        patch(
            "anvil.services.model_import.hf_source._huggingface_hub_available",
            return_value=True,
        ),
        patch(
            "anvil.services.model_import.hf_source._do_download",
            return_value="/tmp/anvil_hf_xxx/model.safetensors",
        ) as mock_dl,
    ):
        source = HfHubSource()
        path = await source.download_asset_to_path(
            "org/model", "model.safetensors", token="tok"
        )
        assert path == "/tmp/anvil_hf_xxx/model.safetensors"
        mock_dl.assert_awaited_once()


@pytest.mark.asyncio
async def test_download_asset_token_fallback(monkeypatch):
    """download_asset_to_path falls back to HF_TOKEN env var."""
    monkeypatch.setenv("HF_TOKEN", "hf_secret_dl")
    captured: dict[str, str | None] = {}

    async def _fake_download(identifier, filename, revision, token, progress_callback):
        captured["token"] = token
        return "/tmp/fake/path"

    with (
        patch(
            "anvil.services.model_import.hf_source._huggingface_hub_available",
            return_value=True,
        ),
        patch(
            "anvil.services.model_import.hf_source._do_download",
            side_effect=_fake_download,
        ),
    ):
        source = HfHubSource()
        await source.download_asset_to_path("org/model", "model.safetensors")
        assert captured["token"] == "hf_secret_dl"


@pytest.mark.asyncio
async def test_list_asset_files_token_fallback(monkeypatch):
    """list_asset_files falls back to HF_TOKEN env var."""
    monkeypatch.setenv("HF_TOKEN", "hf_secret_list")
    captured: dict[str, str | None] = {}

    async def _fake_list_files(identifier, revision, token):
        captured["token"] = token
        return []

    with (
        patch(
            "anvil.services.model_import.hf_source._huggingface_hub_available",
            return_value=True,
        ),
        patch(
            "anvil.services.model_import.hf_source._do_list_files",
            side_effect=_fake_list_files,
        ),
    ):
        source = HfHubSource()
        await source.list_asset_files("org/model")
        assert captured["token"] == "hf_secret_list"


###############################################################################
# Tests for _do_resolve error handling
###############################################################################


class TestDoResolveErrors:
    """Error code mapping in _do_resolve."""

    @pytest.mark.asyncio
    async def test_not_found(self):
        """404 error maps to not_found code."""
        with patch(
            "anvil.services.model_import.hf_source._do_resolve",
        ) as mock_api:
            mock_api.side_effect = ModelSourceError(
                code="not_found", message="not found", source="huggingface"
            )
            source = HfHubSource()
            with patch(
                "anvil.services.model_import.hf_source._huggingface_hub_available",
                return_value=True,
            ):
                with pytest.raises(ModelSourceError) as exc:
                    await source.resolve_metadata("org/model")
                assert exc.value.code == "not_found"

    @pytest.mark.asyncio
    async def test_auth_required(self):
        """401 error maps to auth_required code."""
        with patch(
            "anvil.services.model_import.hf_source._do_resolve",
        ) as mock_api:
            mock_api.side_effect = ModelSourceError(
                code="auth_required", message="auth", source="huggingface"
            )
            source = HfHubSource()
            with patch(
                "anvil.services.model_import.hf_source._huggingface_hub_available",
                return_value=True,
            ):
                with pytest.raises(ModelSourceError) as exc:
                    await source.resolve_metadata("org/model")
                assert exc.value.code == "auth_required"

    @pytest.mark.asyncio
    async def test_rate_limited(self):
        """429 error maps to rate_limited code."""
        with patch(
            "anvil.services.model_import.hf_source._do_resolve",
        ) as mock_api:
            mock_api.side_effect = ModelSourceError(
                code="rate_limited", message="rate", source="huggingface"
            )
            source = HfHubSource()
            with patch(
                "anvil.services.model_import.hf_source._huggingface_hub_available",
                return_value=True,
            ):
                with pytest.raises(ModelSourceError) as exc:
                    await source.resolve_metadata("org/model")
                assert exc.value.code == "rate_limited"

    @pytest.mark.asyncio
    async def test_network_error(self):
        """Connection/timeout error maps to network_error code."""
        with patch(
            "anvil.services.model_import.hf_source._do_resolve",
        ) as mock_api:
            mock_api.side_effect = ModelSourceError(
                code="network_error", message="network", source="huggingface"
            )
            source = HfHubSource()
            with patch(
                "anvil.services.model_import.hf_source._huggingface_hub_available",
                return_value=True,
            ):
                with pytest.raises(ModelSourceError) as exc:
                    await source.resolve_metadata("org/model")
                assert exc.value.code == "network_error"

    @pytest.mark.asyncio
    async def test_parse_failure(self):
        """Unknown error maps to parse_failure code."""
        with patch(
            "anvil.services.model_import.hf_source._do_resolve",
        ) as mock_api:
            mock_api.side_effect = ModelSourceError(
                code="parse_failure", message="parse", source="huggingface"
            )
            source = HfHubSource()
            with patch(
                "anvil.services.model_import.hf_source._huggingface_hub_available",
                return_value=True,
            ):
                with pytest.raises(ModelSourceError) as exc:
                    await source.resolve_metadata("org/model")
                assert exc.value.code == "parse_failure"


###############################################################################
# Tests for _do_list_files error handling
###############################################################################


class TestDoListFilesErrors:
    """Error code mapping in _do_list_files."""

    @pytest.mark.asyncio
    async def test_not_found(self):
        with patch(
            "anvil.services.model_import.hf_source._do_list_files",
        ) as mock_api:
            mock_api.side_effect = ModelSourceError(
                code="not_found", message="not found", source="huggingface"
            )
            source = HfHubSource()
            with patch(
                "anvil.services.model_import.hf_source._huggingface_hub_available",
                return_value=True,
            ):
                with pytest.raises(ModelSourceError) as exc:
                    await source.list_asset_files("org/model")
                assert exc.value.code == "not_found"

    @pytest.mark.asyncio
    async def test_auth_required(self):
        with patch(
            "anvil.services.model_import.hf_source._do_list_files",
        ) as mock_api:
            mock_api.side_effect = ModelSourceError(
                code="auth_required", message="auth", source="huggingface"
            )
            source = HfHubSource()
            with patch(
                "anvil.services.model_import.hf_source._huggingface_hub_available",
                return_value=True,
            ):
                with pytest.raises(ModelSourceError) as exc:
                    await source.list_asset_files("org/model")
                assert exc.value.code == "auth_required"

    @pytest.mark.asyncio
    async def test_rate_limited(self):
        with patch(
            "anvil.services.model_import.hf_source._do_list_files",
        ) as mock_api:
            mock_api.side_effect = ModelSourceError(
                code="rate_limited", message="rate", source="huggingface"
            )
            source = HfHubSource()
            with patch(
                "anvil.services.model_import.hf_source._huggingface_hub_available",
                return_value=True,
            ):
                with pytest.raises(ModelSourceError) as exc:
                    await source.list_asset_files("org/model")
                assert exc.value.code == "rate_limited"

    @pytest.mark.asyncio
    async def test_network_error(self):
        with patch(
            "anvil.services.model_import.hf_source._do_list_files",
        ) as mock_api:
            mock_api.side_effect = ModelSourceError(
                code="network_error", message="network", source="huggingface"
            )
            source = HfHubSource()
            with patch(
                "anvil.services.model_import.hf_source._huggingface_hub_available",
                return_value=True,
            ):
                with pytest.raises(ModelSourceError) as exc:
                    await source.list_asset_files("org/model")
                assert exc.value.code == "network_error"

    @pytest.mark.asyncio
    async def test_parse_failure(self):
        with patch(
            "anvil.services.model_import.hf_source._do_list_files",
        ) as mock_api:
            mock_api.side_effect = ModelSourceError(
                code="parse_failure", message="parse", source="huggingface"
            )
            source = HfHubSource()
            with patch(
                "anvil.services.model_import.hf_source._huggingface_hub_available",
                return_value=True,
            ):
                with pytest.raises(ModelSourceError) as exc:
                    await source.list_asset_files("org/model")
                assert exc.value.code == "parse_failure"


###############################################################################
# Tests for _raise_hf_error
###############################################################################


class TestRaiseHfError:
    """Direct tests for _raise_hf_error helper."""

    def test_not_found(self):
        from anvil.services.model_import.hf_source import _raise_hf_error

        with pytest.raises(ModelSourceError) as exc:
            _raise_hf_error(Exception("404 Not Found"), "org/model", "main")
        assert exc.value.code == "not_found"

    def test_auth_required(self):
        from anvil.services.model_import.hf_source import _raise_hf_error

        with pytest.raises(ModelSourceError) as exc:
            _raise_hf_error(Exception("403 authorization"), "org/model", "main")
        assert exc.value.code == "auth_required"

    def test_rate_limited(self):
        from anvil.services.model_import.hf_source import _raise_hf_error

        with pytest.raises(ModelSourceError) as exc:
            _raise_hf_error(Exception("429 rate limit"), "org/model", "main")
        assert exc.value.code == "rate_limited"

    def test_network_error(self):
        from anvil.services.model_import.hf_source import _raise_hf_error

        with pytest.raises(ModelSourceError) as exc:
            _raise_hf_error(Exception("connection timeout"), "org/model", "main")
        assert exc.value.code == "network_error"

    def test_parse_failure(self):
        from anvil.services.model_import.hf_source import _raise_hf_error

        with pytest.raises(ModelSourceError) as exc:
            _raise_hf_error(Exception("weird error"), "org/model", "main")
        assert exc.value.code == "parse_failure"


###############################################################################
# Tests for _do_resolve metadata extraction
###############################################################################


class TestDoResolveMetadata:
    """Metadata extraction from HF API response."""

    @pytest.mark.asyncio
    async def test_extracts_metadata(self):
        """_do_resolve extracts correct metadata from ModelInfo."""

        class FakeModelInfo:
            id = "org/model"
            safetensors = MagicMock()
            safetensors.parameters = {"BF16": 1000000, "FP32": 500000}
            config = {"architectures": ["LlamaForCausalLM"]}
            sha = "abc123"
            cardData = {"license": "apache-2.0"}
            pipeline_tag = "text-generation"

        fake_hf = MagicMock()
        fake_hf.HfApi.return_value.model_info.return_value = FakeModelInfo()

        with patch.dict("sys.modules", {"huggingface_hub": fake_hf}):
            source = HfHubSource()
            with patch(
                "anvil.services.model_import.hf_source._huggingface_hub_available",
                return_value=True,
            ):
                meta = await source.resolve_metadata("org/model")
            assert meta.display_name == "org/model"
            assert meta.architecture_family == "LlamaForCausalLM"
            assert meta.parameter_count == 1500000
            assert meta.license == "apache-2.0"
            assert meta.revision_sha == "abc123"

    @pytest.mark.asyncio
    async def test_no_safetensors(self):
        """When safetensors is None, parameter_count is 0."""

        class FakeModelInfo2:
            id = "org/model"
            safetensors = None
            config = None
            sha = None
            pipeline_tag = "text-generation"

        fake_hf = MagicMock()
        fake_hf.HfApi.return_value.model_info.return_value = FakeModelInfo2()

        with patch.dict("sys.modules", {"huggingface_hub": fake_hf}):
            source = HfHubSource()
            with patch(
                "anvil.services.model_import.hf_source._huggingface_hub_available",
                return_value=True,
            ):
                meta = await source.resolve_metadata("org/model")
            assert meta.parameter_count == 0
            assert meta.architecture_family == "text-generation"
            assert meta.license == "unknown"
            assert meta.revision_sha == "main"

    @pytest.mark.asyncio
    async def test_no_config(self):
        """When config is None, architecture_family falls back to pipeline_tag."""

        class FakeModelInfo3:
            id = "org/model"
            safetensors = MagicMock()
            safetensors.parameters = None
            config = None
            sha = "def456"
            pipeline_tag = "text-classification"

        fake_hf = MagicMock()
        fake_hf.HfApi.return_value.model_info.return_value = FakeModelInfo3()

        with patch.dict("sys.modules", {"huggingface_hub": fake_hf}):
            source = HfHubSource()
            with patch(
                "anvil.services.model_import.hf_source._huggingface_hub_available",
                return_value=True,
            ):
                meta = await source.resolve_metadata("org/model")
            assert meta.architecture_family == "text-classification"
            assert meta.parameter_count == 0


###############################################################################
# Tests for _do_list_files
###############################################################################


class TestDoListFiles:
    """Asset file listing and categorization."""

    @pytest.mark.asyncio
    async def test_categorizes_assets(self):
        """Files are correctly categorized by type."""
        fake_hf = MagicMock()
        fake_hf.HfApi.return_value.list_repo_files.return_value = [
            "config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "model.safetensors",
            "model-00001-of-00002.safetensors",
            "README.md",
            ".gitattributes",
        ]

        with patch.dict("sys.modules", {"huggingface_hub": fake_hf}):
            from anvil.services.model_import.hf_source import _do_list_files

            assets = await _do_list_files("org/model", "main", None)
            configs = [a for a in assets if a["asset_type"] == "config"]
            tokenizers = [a for a in assets if a["asset_type"] == "tokenizer"]
            weights = [a for a in assets if a["asset_type"] == "weights"]
            assert len(configs) == 1
            assert len(tokenizers) == 2
            assert len(weights) == 2
            assert len(assets) == 5


###############################################################################
# Tests for _do_download
###############################################################################
