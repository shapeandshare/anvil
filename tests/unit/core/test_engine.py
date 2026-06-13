"""Unit tests for the core training engine."""

from microgpt.core.autograd import Value
from microgpt.core.engine import GPT, train
from microgpt.core.tokenizer import Tokenizer


def test_value_backward_multipath():
    a = Value(2.0)
    b = Value(3.0)
    c = a * b
    loss = c + a
    loss.backward()
    assert abs(a.grad - 4.0) < 1e-6
    assert abs(b.grad - 2.0) < 1e-6


def test_value_operations():
    assert (Value(2.0) + Value(3.0)).data == 5.0
    assert (Value(2.0) * Value(3.0)).data == 6.0
    assert Value(-1.0).relu().data == 0.0
    assert Value(2.0).relu().data == 2.0


def test_tokenizer_roundtrip():
    tok = Tokenizer(["emma", "olivia"])
    encoded = tok.encode("emma")
    assert encoded[0] == tok.BOS
    assert encoded[-1] == tok.BOS
    decoded = tok.decode(encoded)
    assert decoded == "emma"


def test_gpt_param_count():
    model = GPT(vocab_size=27, n_embd=16, n_head=4, n_layer=1, block_size=16)
    assert model.num_params() == 4192


def test_train_reduces_loss():
    docs = ["emma", "olivia", "ava", "isabella"]
    _, final_loss, samples, _ = train(docs, num_steps=20, n_embd=8, n_head=2)
    assert final_loss > 0
    assert isinstance(samples, list)
    assert len(samples) == 20
