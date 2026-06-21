# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for Vocabulary helper."""

import tempfile

from anvil.core.engine import LlamaModel, train
from anvil.core.tokenizer import Tokenizer
from anvil.core.vocabulary import Vocabulary


def test_vocabulary_from_chars():
    chars = ["a", "b", "c"]
    vocab = Vocabulary.from_chars(chars)
    assert vocab.vocab_size == len(chars) + 1
    assert vocab.bos_id == len(chars)
    assert vocab.decode([vocab.bos_id]) == ""


def test_vocabulary_encode_decode_roundtrip():
    chars = ["a", "b", "c"]
    vocab = Vocabulary.from_chars(chars)
    encoded = vocab.encode("abc")
    assert encoded[0] == vocab.bos_id
    assert encoded[-1] == vocab.bos_id
    assert encoded[1:-1] == [0, 1, 2]
    decoded = vocab.decode(encoded)
    assert decoded == "abc"


def test_vocabulary_decode_skips_bos():
    chars = ["x", "y", "z"]
    vocab = Vocabulary.from_chars(chars)
    result = vocab.decode([vocab.bos_id, 0, 1, 2, vocab.bos_id])
    assert result == "xyz"


def test_vocabulary_parity_with_tokenizer():
    """Vocabulary.from_chars should produce same encode/decode as Tokenizer."""
    docs = ["emma", "olivia", "ava"]
    tok = Tokenizer(docs)
    vocab = Vocabulary.from_chars(tok.uchars)

    for doc in docs:
        tok_enc = tok.encode(doc)
        voc_enc = vocab.encode(doc)
        assert tok_enc == voc_enc, f"Mismatch encoding {doc!r}"
        tok_dec = tok.decode(tok_enc)
        voc_dec = vocab.decode(voc_enc)
        assert tok_dec == voc_dec, f"Mismatch decoding {doc!r}"

    assert tok.BOS == vocab.bos_id
    assert tok.vocab_size == vocab.vocab_size


def test_vocabulary_from_trained_model():
    """Chars from a trained model save/load should produce working Vocabulary."""
    docs = ["emma", "olivia", "ava"]
    model, _, _, uchars = train(docs, num_steps=5, n_embd=8, n_head=2)

    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        model.save(f.name, uchars)

        loaded = LlamaModel.load(f.name)
        loaded_vocab = Vocabulary.from_chars(loaded.chars)

        tok = Tokenizer(docs)
        for doc in docs:
            assert loaded_vocab.encode(doc) == tok.encode(doc)
            assert loaded_vocab.decode(tok.encode(doc)) == tok.decode(tok.encode(doc))
