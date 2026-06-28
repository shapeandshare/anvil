"""Tests for TokenizerFactory — dispatch, error paths, and NMRG old-checkpoint loading."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from anvil.services._shared.tokenizer_load_error import TokenizerLoadError
from anvil.services.inference.tokenizer_factory import create_tokenizer


class TestTokenizerFactory:
    """Test the tokenizer factory dispatch and error handling."""

    def test_char_json_no_chars(self) -> None:
        """char_json without chars raises TokenizerLoadError."""
        with pytest.raises(TokenizerLoadError, match="character list"):
            create_tokenizer(
                tokenizer_family="char",
                serialization_type="char_json",
                chars=None,
            )

    def test_unknown_family(self) -> None:
        """Unknown tokenizer family raises TokenizerLoadError."""
        with pytest.raises(TokenizerLoadError, match="Unknown tokenizer family"):
            create_tokenizer(
                tokenizer_family="nonexistent",
                serialization_type="char_json",
                chars=["a", "b"],
            )

    def test_unsupported_serialization(self) -> None:
        """Unsupported serialization type raises TokenizerLoadError."""
        with pytest.raises(TokenizerLoadError, match="Unsupported serialization type"):
            create_tokenizer(
                tokenizer_family="subword",
                serialization_type="wordpiece",
                artifact_dir="/tmp",
            )

    def test_hf_fast_missing_file(self) -> None:
        """Missing tokenizer.json raises TokenizerLoadError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(TokenizerLoadError, match="tokenizer.json"):
                create_tokenizer(
                    tokenizer_family="subword",
                    serialization_type="hf_fast",
                    artifact_dir=tmpdir,
                )

    def test_sentencepiece_missing_file(self) -> None:
        """Missing .model file raises TokenizerLoadError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(TokenizerLoadError, match="not found"):
                create_tokenizer(
                    tokenizer_family="subword",
                    serialization_type="sentencepiece",
                    artifact_dir=tmpdir,
                )

    def test_subword_requires_artifact_dir(self) -> None:
        """Subword tokenizer without artifact_dir raises TokenizerLoadError."""
        with pytest.raises(TokenizerLoadError, match="artifact directory"):
            create_tokenizer(
                tokenizer_family="subword",
                serialization_type="hf_fast",
            )

    def test_nmrg_old_checkpoint_defaults_to_char(self) -> None:
        """TokenizerFactory creates char tokenizer when explicit family=char (simulating old checkpoint)."""
        vocab = create_tokenizer(
            tokenizer_family="char",
            serialization_type="char_json",
            chars=["a", "b", "c"],
        )
        assert vocab.vocab_size == 4  # 3 chars + BOS
        assert vocab.bos_id == 3


class TestTokenizerFactoryIntegration:
    """Integration-level tests for the factory."""

    def test_char_tokenizer_roundtrip(self) -> None:
        """Factory-created char tokenizer round-trips correctly."""
        tok = create_tokenizer(
            tokenizer_family="char",
            serialization_type="char_json",
            chars=list("hello world"),
        )
        ids = tok.encode("hello")
        assert tok.decode(ids) == "hello"

    def test_factory_creates_tokenizer_instance(self) -> None:
        """Factory returns a Tokenizer protocol instance."""
        from anvil.core._tokenizer_base import Tokenizer

        tok = create_tokenizer(
            tokenizer_family="char",
            serialization_type="char_json",
            chars=["a", "b"],
        )
        assert isinstance(tok, Tokenizer)

    def test_error_has_file_path_and_cause(self) -> None:
        """TokenizerLoadError includes file_path and cause."""
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                create_tokenizer(
                    tokenizer_family="subword",
                    serialization_type="hf_fast",
                    artifact_dir=tmpdir,
                )
            except TokenizerLoadError as e:
                assert e.file_path is not None
                assert e.cause is not None
            else:
                pytest.fail("Expected TokenizerLoadError")
