"""Unit tests for ModelRef and derive_catalog_name."""

# pylint: disable=missing-function-docstring

import pytest
from pydantic import ValidationError

from anvil.services._shared.source_type import SourceType
from anvil.services.catalog.model_ref import ModelRef, derive_catalog_name


class TestModelRef:
    def test_valid_ref(self) -> None:
        ref = ModelRef(name="hf--TinyLlama--TinyLlama-1.1B", version=1)
        assert ref.name == "hf--TinyLlama--TinyLlama-1.1B"
        assert ref.version == 1

    def test_frozen(self) -> None:
        ref = ModelRef(name="test-model", version=1)
        with pytest.raises(ValidationError):
            ref.name = "changed"  # type: ignore[misc]

    def test_string_form(self) -> None:
        ref = ModelRef(name="test-model", version=3)
        assert str(ref) == "test-model/3"

    def test_invalid_name_rejects_slash(self) -> None:
        with pytest.raises(ValidationError):
            ModelRef(name="invalid/name", version=1)

    def test_invalid_name_rejects_colon(self) -> None:
        with pytest.raises(ValidationError):
            ModelRef(name="invalid:name", version=1)

    def test_invalid_name_rejects_spaces(self) -> None:
        with pytest.raises(ValidationError):
            ModelRef(name="invalid name", version=1)

    def test_invalid_name_rejects_unicode(self) -> None:
        with pytest.raises(ValidationError):
            ModelRef(name="héllo", version=1)

    def test_zero_version_invalid(self) -> None:
        with pytest.raises(ValidationError):
            ModelRef(name="test", version=0)

    def test_empty_name_invalid(self) -> None:
        with pytest.raises(ValidationError):
            ModelRef(name="", version=1)

    def test_valid_chars_accepted(self) -> None:
        ref = ModelRef(name="a.B-c_d-e", version=42)
        assert ref.name == "a.B-c_d-e"
        assert ref.version == 42


class TestDeriveCatalogName:
    def test_hf_source(self) -> None:
        result = derive_catalog_name(SourceType.HUGGINGFACE, "TinyLlama/TinyLlama-1.1B")
        assert result == "hf--TinyLlama-TinyLlama-1.1B"

    def test_local_source(self) -> None:
        result = derive_catalog_name(SourceType.LOCAL, "my-models/test")
        assert result == "local--my-models-test"

    def test_sanitizes_special_chars(self) -> None:
        result = derive_catalog_name(
            SourceType.HUGGINGFACE, "meta-llama/Llama-3.2-1B-Instruct"
        )
        assert "/" not in result
        assert result == "hf--meta-llama-Llama-3.2-1B-Instruct"

    def test_deterministic(self) -> None:
        r1 = derive_catalog_name(SourceType.HUGGINGFACE, "repo/model")
        r2 = derive_catalog_name(SourceType.HUGGINGFACE, "repo/model")
        assert r1 == r2

    def test_accepts_string_source_type(self) -> None:
        result = derive_catalog_name("local", "some/path")
        assert result == "local--some-path"

    def test_prefixes_differentiate_providers(self) -> None:
        hf_name = derive_catalog_name(SourceType.HUGGINGFACE, "org/model")
        local_name = derive_catalog_name(SourceType.LOCAL, "org/model")
        assert hf_name != local_name
        assert hf_name.startswith("hf--")
        assert local_name.startswith("local--")
