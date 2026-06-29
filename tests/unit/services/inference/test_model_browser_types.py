# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the HuggingFace Model Browser Pydantic models.

Tests validate that ``ResourceEnvelope``, ``CatalogEntry``, and
``CuratedCatalog`` enforce their field constraints and parse YAML
catalog data correctly.
"""

import pytest
import yaml
from pydantic import ValidationError

from anvil.services.inference.catalog_entry import CatalogEntry
from anvil.services.inference.curated_catalog import CuratedCatalog
from anvil.services.inference.resource_envelope import ResourceEnvelope


def test_resource_envelope_rejects_negative_min_ram_gb():
    """ResourceEnvelope raises ValidationError when min_ram_gb is negative."""
    with pytest.raises(ValidationError):
        ResourceEnvelope(
            min_ram_gb=-1.0,
            min_vram_per_backend={"cpu": 0.0, "cuda": 4.0},
            supported_methods=["lora"],
        )


def test_resource_envelope_rejects_missing_cpu_key():
    """ResourceEnvelope raises ValidationError when min_vram_per_backend lacks 'cpu'."""
    with pytest.raises(ValidationError):
        ResourceEnvelope(
            min_ram_gb=8.0,
            min_vram_per_backend={"cuda": 4.0},
            supported_methods=["lora"],
        )


def test_resource_envelope_rejects_empty_supported_methods():
    """ResourceEnvelope raises ValidationError when supported_methods is empty."""
    with pytest.raises(ValidationError):
        ResourceEnvelope(
            min_ram_gb=8.0,
            min_vram_per_backend={"cpu": 0.0, "cuda": 4.0},
            supported_methods=[],
        )


def test_resource_envelope_accepts_valid_data():
    """ResourceEnvelope constructs successfully with all valid fields."""
    envelope = ResourceEnvelope(
        min_ram_gb=8.0,
        min_vram_per_backend={"cpu": 0.0, "cuda": 4.0, "mps": 6.0},
        supported_methods=["lora"],
    )
    assert envelope.min_ram_gb == 8.0
    assert envelope.min_vram_per_backend["cpu"] == 0.0
    assert envelope.supported_methods == ["lora"]


def test_resource_envelope_accepts_zero_min_ram_gb():
    """ResourceEnvelope accepts min_ram_gb of exactly 0 (boundary of ge=0)."""
    envelope = ResourceEnvelope(
        min_ram_gb=0.0,
        min_vram_per_backend={"cpu": 0.0},
        supported_methods=["lora"],
    )
    assert envelope.min_ram_gb == 0.0


def test_resource_envelope_accepts_multiple_methods():
    """ResourceEnvelope accepts a list with multiple supported methods."""
    envelope = ResourceEnvelope(
        min_ram_gb=8.0,
        min_vram_per_backend={"cpu": 0.0, "cuda": 4.0},
        supported_methods=["lora", "full", "qlora"],
    )
    assert len(envelope.supported_methods) == 3


def test_catalog_entry_accepts_valid_data():
    """CatalogEntry constructs successfully with all required fields."""
    entry = CatalogEntry(
        hf_id="test/model",
        display_name="Test Model",
        params="1.1B",
        license="MIT",
        architecture="LlamaForCausalLM",
        tokenizer_family="SentencePiece",
        url="https://huggingface.co/test/model",
        tags=["test", "base"],
        resource_envelope=ResourceEnvelope(
            min_ram_gb=8.0,
            min_vram_per_backend={"cpu": 0.0, "cuda": 4.0},
            supported_methods=["lora"],
        ),
    )
    assert entry.hf_id == "test/model"
    assert len(entry.tags) == 2
    assert entry.resource_envelope.min_ram_gb == 8.0


def test_catalog_entry_defaults_tags_to_empty_list():
    """CatalogEntry defaults tags to an empty list when omitted."""
    entry = CatalogEntry(
        hf_id="test/model",
        display_name="Test Model",
        params="1.1B",
        license="MIT",
        architecture="LlamaForCausalLM",
        tokenizer_family="SentencePiece",
        url="https://huggingface.co/test/model",
        resource_envelope=ResourceEnvelope(
            min_ram_gb=8.0,
            min_vram_per_backend={"cpu": 0.0},
            supported_methods=["lora"],
        ),
    )
    assert entry.tags == []


def test_catalog_entry_rejects_missing_hf_id():
    """CatalogEntry raises ValidationError when hf_id is omitted."""
    with pytest.raises(ValidationError):
        CatalogEntry(
            display_name="Test Model",
            params="1.1B",
            license="MIT",
            architecture="LlamaForCausalLM",
            tokenizer_family="SentencePiece",
            url="https://huggingface.co/test/model",
            resource_envelope=ResourceEnvelope(
                min_ram_gb=8.0,
                min_vram_per_backend={"cpu": 0.0},
                supported_methods=["lora"],
            ),
        )


def test_catalog_entry_rejects_missing_resource_envelope():
    """CatalogEntry raises ValidationError when resource_envelope is omitted."""
    with pytest.raises(ValidationError):
        CatalogEntry(
            hf_id="test/model",
            display_name="Test Model",
            params="1.1B",
            license="MIT",
            architecture="LlamaForCausalLM",
            tokenizer_family="SentencePiece",
            url="https://huggingface.co/test/model",
        )


def test_catalog_entry_rejects_invalid_resource_envelope():
    """CatalogEntry raises ValidationError when resource_envelope has invalid data."""
    with pytest.raises(ValidationError):
        CatalogEntry(
            hf_id="test/model",
            display_name="Test Model",
            params="1.1B",
            license="MIT",
            architecture="LlamaForCausalLM",
            tokenizer_family="SentencePiece",
            url="https://huggingface.co/test/model",
            resource_envelope={
                "min_ram_gb": -1.0,
                "min_vram_per_backend": {"cuda": 4.0},
                "supported_methods": [],
            },
        )


def test_curated_catalog_parses_minimal_yaml():
    """CuratedCatalog loads correctly from a minimal YAML string."""
    yaml_str = """\
catalog:
  - hf_id: "test/model"
    display_name: "Test Model"
    params: "1.1B"
    license: "MIT"
    architecture: "LlamaForCausalLM"
    tokenizer_family: "SentencePiece"
    url: "https://huggingface.co/test/model"
    tags:
      - "test"
      - "base"
    resource_envelope:
      min_ram_gb: 8.0
      min_vram_per_backend:
        cpu: 0
        cuda: 4.0
      supported_methods:
        - "lora"
"""
    data = yaml.safe_load(yaml_str)
    catalog = CuratedCatalog.model_validate(data)
    assert len(catalog.catalog) == 1
    entry = catalog.catalog[0]
    assert entry.hf_id == "test/model"
    assert entry.display_name == "Test Model"
    assert entry.params == "1.1B"
    assert entry.license == "MIT"
    assert entry.architecture == "LlamaForCausalLM"
    assert entry.tokenizer_family == "SentencePiece"
    assert entry.url == "https://huggingface.co/test/model"
    assert entry.tags == ["test", "base"]
    assert entry.resource_envelope.min_ram_gb == 8.0
    assert entry.resource_envelope.min_vram_per_backend["cpu"] == 0.0
    assert entry.resource_envelope.min_vram_per_backend["cuda"] == 4.0
    assert entry.resource_envelope.supported_methods == ["lora"]


def test_curated_catalog_parses_multi_entry_yaml():
    """CuratedCatalog loads multiple entries from a YAML string."""
    yaml_str = """\
catalog:
  - hf_id: "model/a"
    display_name: "Model A"
    params: "500M"
    license: "MIT"
    architecture: "LlamaForCausalLM"
    tokenizer_family: "SentencePiece"
    url: "https://huggingface.co/model/a"
    resource_envelope:
      min_ram_gb: 4.0
      min_vram_per_backend:
        cpu: 0
        cuda: 2.0
      supported_methods:
        - "lora"
  - hf_id: "model/b"
    display_name: "Model B"
    params: "1B"
    license: "Apache-2.0"
    architecture: "LlamaForCausalLM"
    tokenizer_family: "BPE"
    url: "https://huggingface.co/model/b"
    resource_envelope:
      min_ram_gb: 8.0
      min_vram_per_backend:
        cpu: 0
        cuda: 4.0
      supported_methods:
        - "lora"
        - "full"
"""
    data = yaml.safe_load(yaml_str)
    catalog = CuratedCatalog.model_validate(data)
    assert len(catalog.catalog) == 2
    assert catalog.catalog[0].hf_id == "model/a"
    assert catalog.catalog[1].hf_id == "model/b"
    assert catalog.catalog[1].resource_envelope.supported_methods == ["lora", "full"]


def test_curated_catalog_accepts_empty_catalog():
    """CuratedCatalog accepts an empty catalog list (no min_length constraint)."""
    catalog = CuratedCatalog(catalog=[])
    assert catalog.catalog == []


def test_curated_catalog_rejects_missing_catalog_key():
    """CuratedCatalog raises ValidationError when catalog key is missing."""
    data = {"not_catalog": []}
    with pytest.raises(ValidationError):
        CuratedCatalog.model_validate(data)


def test_curated_catalog_rejects_invalid_entry_in_yaml():
    """CuratedCatalog raises ValidationError when a catalog entry is missing required fields."""
    yaml_str = """\
catalog:
  - hf_id: "test/model"
    display_name: "Test Model"
"""
    data = yaml.safe_load(yaml_str)
    with pytest.raises(ValidationError):
        CuratedCatalog.model_validate(data)
