# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for the HuggingFace Hub ModelSource.

Mocks ``_do_resolve`` and the availability probe so no network calls
and no ``huggingface_hub`` dependency are required.
"""

from __future__ import annotations

from unittest.mock import patch

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
