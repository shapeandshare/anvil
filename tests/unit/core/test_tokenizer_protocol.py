"""Contract tests for the Tokenizer protocol — char-level parity and unicode edge cases."""

from __future__ import annotations

from anvil.core._tokenizer_base import Tokenizer
from anvil.core.vocabulary import Vocabulary


def _make_vocab() -> Vocabulary:
    return Vocabulary.from_chars(sorted({"a", "b", "c", "d", "e", " "}))


class TestTokenizerProtocol:
    """Verify Vocabulary implements the Tokenizer protocol correctly."""

    def test_protocol_inheritance(self) -> None:
        """Vocabulary is a Tokenizer."""
        vocab = _make_vocab()
        assert isinstance(vocab, Tokenizer)

    def test_encode_roundtrip(self) -> None:
        """Round-trip encode/decode reproduces input."""
        vocab = _make_vocab()
        text = "a b c d e"
        ids = vocab.encode(text)
        decoded = vocab.decode(ids)
        assert decoded == text

    def test_encode_adds_bos(self) -> None:
        """Encode wraps with BOS markers."""
        vocab = _make_vocab()
        ids = vocab.encode("a")
        assert ids[0] == vocab.bos_id
        assert ids[-1] == vocab.bos_id

    def test_decode_strips_bos(self) -> None:
        """Decode strips BOS markers from output."""
        vocab = _make_vocab()
        raw = vocab.encode("a")
        decoded = vocab.decode(raw)
        assert "<BOS>" not in decoded

    def test_bos_id_is_int(self) -> None:
        """Char-level bos_id returns an int, not None."""
        vocab = _make_vocab()
        assert isinstance(vocab.bos_id, int)
        assert vocab.bos_id == len(vocab.chars)

    def test_vocab_size(self) -> None:
        """Vocab size is len(chars) + 1 (includes BOS)."""
        vocab = _make_vocab()
        assert vocab.vocab_size == len(vocab.chars) + 1

    def test_unknown_char_skipped(self) -> None:
        """Characters not in vocabulary are silently skipped."""
        vocab = _make_vocab()
        ids = vocab.encode("xyz")  # x, y, z not in {a,b,c,d,e," "}
        # Only BOS tokens remain
        assert len(ids) == 2
        assert ids[0] == vocab.bos_id
        assert ids[-1] == vocab.bos_id

    def test_empty_string(self) -> None:
        """Empty string encodes to just BOS tokens."""
        vocab = _make_vocab()
        ids = vocab.encode("")
        assert ids == [vocab.bos_id, vocab.bos_id]
        assert vocab.decode(ids) == ""

    def test_decode_empty_list(self) -> None:
        """Empty list decodes to empty string."""
        vocab = _make_vocab()
        assert vocab.decode([]) == ""

    def test_decode_skips_oob_ids(self) -> None:
        """Out-of-range IDs are silently skipped."""
        vocab = _make_vocab()
        result = vocab.decode([9999, vocab.bos_id, -1])
        assert isinstance(result, str)


class TestUnicodeEdgeCases:
    """Unicode contract tests per spec: emoji, CJK, combining diacritics, null."""

    def test_emoji_surrogate_pairs(self) -> None:
        """Emoji characters round-trip correctly."""
        chars = list("ab😀🎉🌟")
        vocab = Vocabulary.from_chars(chars)
        text = "a😀b🎉🌟"
        ids = vocab.encode(text)
        decoded = vocab.decode(ids)
        assert decoded == text

    def test_cjk_ideographs(self) -> None:
        """CJK characters round-trip correctly."""
        chars = list("abc中文你好")
        vocab = Vocabulary.from_chars(chars)
        text = "你好中文"
        ids = vocab.encode(text)
        decoded = vocab.decode(ids)
        assert decoded == text

    def test_combining_diacritics(self) -> None:
        """Combining diacritical marks round-trip."""
        combining_acute = "\u0301"
        chars = sorted({"a", "c", "e", combining_acute, "f"})
        vocab = Vocabulary.from_chars(chars)
        text = f"a{combining_acute}c"
        ids = vocab.encode(text)
        decoded = vocab.decode(ids)
        assert decoded == text

    def test_null_character(self) -> None:
        """Null character is handled (skipped if not in vocab)."""
        vocab = _make_vocab()
        text = "a\x00b"
        ids = vocab.encode(text)
        decoded = vocab.decode(ids)
        # null is skipped if not in vocab
        assert "\x00" not in decoded
        assert "a" in decoded
        assert "b" in decoded
