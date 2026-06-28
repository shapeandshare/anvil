# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for the local file ModelSource."""

from __future__ import annotations

import json

import pytest

from anvil.services._shared.import_types import ModelSourceError
from anvil.services.model_import.local_source import LocalSource


@pytest.mark.asyncio
async def test_local_source_returns_metadata(tmp_path):
    """Given a directory with config.json, resolve_metadata returns ModelMetadata."""
    config = {
        "_name_or_path": "test-model",
        "architectures": ["LlamaForCausalLM"],
        "hidden_size": 256,
        "num_hidden_layers": 4,
        "intermediate_size": 512,
        "num_attention_heads": 4,
        "vocab_size": 32000,
        "license": "mit",
    }
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")

    source = LocalSource()
    meta = await source.resolve_metadata(str(tmp_path))

    assert meta.display_name == "test-model"
    assert meta.architecture_family == "LlamaForCausalLM"
    assert meta.parameter_count > 0
    assert meta.license == "mit"
    assert meta.revision_sha == "local"


@pytest.mark.asyncio
async def test_local_source_not_found(tmp_path):
    """Given a non-existent path, resolve_metadata raises not_found error."""
    source = LocalSource()
    with pytest.raises(ModelSourceError) as exc:
        await source.resolve_metadata(str(tmp_path / "nonexistent"))
    assert exc.value.code == "not_found"


@pytest.mark.asyncio
async def test_local_source_not_a_directory(tmp_path):
    """Given a file path instead of a directory, resolve_metadata raises
    invalid_identifier.
    """
    f = tmp_path / "not_a_dir"
    f.write_text("whatever", encoding="utf-8")

    source = LocalSource()
    with pytest.raises(ModelSourceError) as exc:
        await source.resolve_metadata(str(f))
    assert exc.value.code == "invalid_identifier"


@pytest.mark.asyncio
async def test_local_source_missing_config(tmp_path):
    """Given a directory without config.json, resolve_metadata raises
    parse_failure.
    """
    (tmp_path / "some_other_file.txt").write_text("x", encoding="utf-8")

    source = LocalSource()
    with pytest.raises(ModelSourceError) as exc:
        await source.resolve_metadata(str(tmp_path))
    assert exc.value.code == "parse_failure"


@pytest.mark.asyncio
async def test_local_source_with_tokenizer_config(tmp_path):
    """When tokenizer_config.json exists, tokenizer_family is extracted."""
    config = {
        "_name_or_path": "tok-test",
        "architectures": ["LlamaForCausalLM"],
        "hidden_size": 64,
        "num_hidden_layers": 1,
        "intermediate_size": 128,
        "vocab_size": 1000,
        "license": "apache-2.0",
    }
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    tok_config = {"tokenizer_class": "LlamaTokenizer"}
    (tmp_path / "tokenizer_config.json").write_text(
        json.dumps(tok_config), encoding="utf-8"
    )

    source = LocalSource()
    meta = await source.resolve_metadata(str(tmp_path))

    assert meta.tokenizer_family == "LlamaTokenizer"