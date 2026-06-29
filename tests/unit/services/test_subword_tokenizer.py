"""Tests for HF subword tokenizer wrappers — requires [finetune] extra."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

try:
    from tokenizers import Tokenizer as _HFTokenizer

    HAS_FINETUNE = True
except ImportError:
    HAS_FINETUNE = False


pytestmark = pytest.mark.skipif(
    not HAS_FINETUNE,
    reason="Requires [finetune] extra: pip install anvil[finetune]",
)


def _make_minimal_tokenizer_json(tmpdir: str) -> str:
    """Create a minimal BPE tokenizer.json for testing."""
    path = os.path.join(tmpdir, "tokenizer.json")
    data = {
        "version": "1.0",
        "truncation": None,
        "padding": None,
        "added_tokens": [],
        "normalizer": {"type": "NFC"},
        "pre_tokenizer": {"type": "Whitespace"},
        "post_processor": None,
        "decoder": {
            "type": "ByteLevel",
            "add_prefix_space": True,
            "trim_offsets": True,
            "use_regex": True,
        },
        "model": {
            "type": "BPE",
            "dropout": None,
            "unk_token": None,
            "continuing_subword_prefix": None,
            "end_of_word_suffix": None,
            "fuse_unk": False,
            "byte_fallback": False,
            "vocab": {"a": 0, "b": 1, " ": 2},
            "merges": [],
        },
    }
    with open(path, "w") as f:
        json.dump(data, f)
    return path


class TestHFFastTokenizer:
    """Test the HFFastTokenizer wrapper."""

    def test_from_file_and_roundtrip(self) -> None:
        """Load a tokenizer.json and round-trip text through the wrapper."""
        from anvil.services.inference._subword_tokenizer import HFFastTokenizer

        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_minimal_tokenizer_json(tmpdir)
            tok = HFFastTokenizer.from_file(path)
            text = "a b c"
            ids = tok.encode(text)
            decoded = tok.decode(ids)
            assert isinstance(ids, list)
            assert all(isinstance(i, int) for i in ids)
            assert isinstance(decoded, str)

    def test_vocab_size(self) -> None:
        """vocab_size returns a positive int."""
        from anvil.services.inference._subword_tokenizer import HFFastTokenizer

        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_minimal_tokenizer_json(tmpdir)
            tok = HFFastTokenizer.from_file(path)
            assert tok.vocab_size > 0

    def test_bos_id_is_none(self) -> None:
        """HFFastTokenizer.bos_id returns None."""
        from anvil.services.inference._subword_tokenizer import HFFastTokenizer

        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_minimal_tokenizer_json(tmpdir)
            tok = HFFastTokenizer.from_file(path)
            assert tok.bos_id is None

    def test_implements_tokenizer(self) -> None:
        """HFFastTokenizer is a Tokenizer."""
        from anvil.core._tokenizer_base import Tokenizer
        from anvil.services.inference._subword_tokenizer import HFFastTokenizer

        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_minimal_tokenizer_json(tmpdir)
            tok = HFFastTokenizer.from_file(path)
            assert isinstance(tok, Tokenizer)
