"""Tests for SentencePiece tokenizer wrapper — requires [finetune] extra.

Mirrors the ``test_subword_tokenizer.py`` pattern.
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

try:
    import sentencepiece as _sp

    HAS_FINETUNE = True
except ImportError:
    HAS_FINETUNE = False


pytestmark = pytest.mark.skipif(
    not HAS_FINETUNE,
    reason="Requires [finetune] extra: pip install anvil[finetune]",
)


def _make_mock_processor() -> MagicMock:
    """Create a mock SentencePiece processor for testing.

    Returns a MagicMock that implements the minimal interface used by
    ``SentencePieceTokenizer``: ``encode``, ``decode``, and
    ``get_piece_size``.
    """
    processor = MagicMock()
    processor.encode.side_effect = lambda text: [ord(c) for c in text]
    processor.decode.side_effect = lambda ids: "".join(chr(i) for i in ids)
    processor.get_piece_size.return_value = 32000
    return processor


class TestSentencePieceTokenizer:
    """Test the SentencePieceTokenizer wrapper."""

    def test_raises_import_error_when_not_installed(self) -> None:
        """Raises ImportError when sentencepiece is not available."""
        with patch(
            "anvil.services.inference._sentencepiece_tokenizer._HAS_SP_DEPS",
            False,
        ):
            from anvil.services.inference._sentencepiece_tokenizer import (
                SentencePieceTokenizer,
            )

            with pytest.raises(ImportError, match="sentencepiece library is required"):
                SentencePieceTokenizer.from_file("/fake/path.model")

    def test_from_file_and_roundtrip(self) -> None:
        """Load via factory and round-trip text through encode/decode."""
        from anvil.services.inference._sentencepiece_tokenizer import (
            SentencePieceTokenizer,
        )

        processor = _make_mock_processor()

        with (
            patch(
                "anvil.services.inference._sentencepiece_tokenizer._sentencepiece_lib.SentencePieceProcessor",
            ) as mock_sp_cls,
        ):
            mock_sp_cls.return_value = processor
            tok = SentencePieceTokenizer.from_file("/fake/path.model")

        # Verify the processor was created and load was called
        mock_sp_cls.assert_called_once()
        processor.load.assert_called_once_with("/fake/path.model")

        # Round-trip
        text = "hello world"
        ids = tok.encode(text)
        decoded = tok.decode(ids)
        assert isinstance(ids, list)
        assert all(isinstance(i, int) for i in ids)
        assert isinstance(decoded, str)
        assert decoded == text

    def test_encode_empty_string(self) -> None:
        """Encoding an empty string returns an empty list."""
        from anvil.services.inference._sentencepiece_tokenizer import (
            SentencePieceTokenizer,
        )

        processor = _make_mock_processor()
        processor.encode.side_effect = lambda text: []

        tok = SentencePieceTokenizer(processor)
        ids = tok.encode("")
        assert ids == []

    def test_decode_empty_list(self) -> None:
        """Decoding an empty list returns an empty string."""
        from anvil.services.inference._sentencepiece_tokenizer import (
            SentencePieceTokenizer,
        )

        processor = _make_mock_processor()
        processor.decode.side_effect = lambda ids: ""

        tok = SentencePieceTokenizer(processor)
        decoded = tok.decode([])
        assert decoded == ""

    def test_vocab_size(self) -> None:
        """vocab_size returns a positive int."""
        from anvil.services.inference._sentencepiece_tokenizer import (
            SentencePieceTokenizer,
        )

        processor = _make_mock_processor()
        tok = SentencePieceTokenizer(processor)
        assert tok.vocab_size == 32000

    def test_bos_id_is_none(self) -> None:
        """SentencePieceTokenizer.bos_id returns None."""
        from anvil.services.inference._sentencepiece_tokenizer import (
            SentencePieceTokenizer,
        )

        processor = _make_mock_processor()
        tok = SentencePieceTokenizer(processor)
        assert tok.bos_id is None

    def test_implements_tokenizer(self) -> None:
        """SentencePieceTokenizer is a Tokenizer."""
        from anvil.core._tokenizer_base import Tokenizer
        from anvil.services.inference._sentencepiece_tokenizer import (
            SentencePieceTokenizer,
        )

        processor = _make_mock_processor()
        tok = SentencePieceTokenizer(processor)
        assert isinstance(tok, Tokenizer)

    def test_constructor_stores_processor(self) -> None:
        """Constructor stores the given processor."""
        from anvil.services.inference._sentencepiece_tokenizer import (
            SentencePieceTokenizer,
        )

        processor = _make_mock_processor()
        tok = SentencePieceTokenizer(processor)
        assert tok._processor is processor
