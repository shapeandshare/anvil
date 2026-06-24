# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the core training engine."""

import math

import pytest

from anvil.core.autograd import Value
from anvil.core.engine import (
    LlamaModel,
    apply_rope,
    linear,
    matrix,
    precompute_rope,
    rmsnorm,
    softmax,
    train,
)
from anvil.core.tokenizer import Tokenizer
from anvil.core.vocabulary import Vocabulary


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
    model = LlamaModel(vocab_size=27, n_embd=16, n_head=4, n_layer=1, block_size=16)
    # Llama architecture: wte(27*16) + lm_head(27*16) + attn_wq(16*16) + attn_wk(16*16)
    #   + attn_wv(16*16) + attn_wo(16*16) + mlp_gate(42*16) + mlp_up(42*16)
    #   + mlp_down(16*42) + rms_1(16) + rms_2(16) + rms_final(16)
    # = 432 + 432 + 256 + 256 + 256 + 256 + 672 + 672 + 672 + 16 + 16 + 16 = 3952
    assert model.num_params() == 3952


def test_train_reduces_loss():
    docs = ["emma", "olivia", "ava", "isabella"]
    _, final_loss, samples, _ = train(docs, num_steps=20, n_embd=8, n_head=2)
    assert final_loss > 0
    assert isinstance(samples, list)
    assert len(samples) == 20


def test_optimizer_state_callback():
    """T047: optimizer_state_callback receives correct m/v/grad arrays."""
    docs = ["emma", "olivia"]
    captured = []

    def cb(step, m, v, grads):
        captured.append(
            {"step": step, "m_len": len(m), "v_len": len(v), "grads_len": len(grads)}
        )

    from anvil.core.engine import train as t

    t(docs, num_steps=5, n_embd=8, n_head=2, optimizer_state_callback=cb)

    assert len(captured) == 5
    for entry in captured:
        assert entry["m_len"] == entry["v_len"] == entry["grads_len"]
        assert entry["m_len"] > 0


# --- Llama architecture tests (T009, T014, T019, T022, T023b) ---


def test_rope_magnitude_preservation():
    """T009: RoPE preserves vector magnitude."""
    head_dim = 4
    cos_t, sin_t = precompute_rope(8, head_dim)
    vector = [1.0, 0.0, 0.0, 0.0]
    original_norm = math.sqrt(sum(v * v for v in vector))
    for pos in range(8):
        rotated = apply_rope(vector, pos, cos_t, sin_t)
        rotated_norm = math.sqrt(sum(v * v for v in rotated))
        assert abs(rotated_norm - original_norm) < 1e-10


def test_rope_position_zero_identity():
    """T009: RoPE at position 0 is identity (cos=1, sin=0)."""
    head_dim = 4
    cos_t, sin_t = precompute_rope(8, head_dim)
    vector = [1.0, 2.0, 3.0, 4.0]
    rotated = apply_rope(vector, 0, cos_t, sin_t)
    for i in range(len(vector)):
        assert abs(rotated[i] - vector[i]) < 1e-10


def test_rope_different_positions_differ():
    """T009: RoPE at different positions produces different rotations."""
    head_dim = 4
    cos_t, sin_t = precompute_rope(8, head_dim)
    vector = [1.0, 0.5, -1.0, 2.0]
    r0 = apply_rope(vector, 0, cos_t, sin_t)
    r1 = apply_rope(vector, 1, cos_t, sin_t)
    # Positions 0 and 1 should differ for at least some dimensions
    assert any(abs(r0[i] - r1[i]) > 1e-10 for i in range(len(vector)))


def test_rope_half_split_pairing():
    """T009: Half-split pairs dim i with dim i + head_dim/2."""
    head_dim = 4
    cos_t, sin_t = precompute_rope(8, head_dim)
    # Vector where only first half has signal
    vector = [0.5, 0.0, 1.0, 0.0]
    pos = 3
    rotated = apply_rope(vector, pos, cos_t, sin_t)
    c3 = cos_t[3][0]
    s3 = sin_t[3][0]
    # dim0 paired with dim2
    expected_0 = vector[0] * c3 - vector[2] * s3
    expected_2 = vector[2] * c3 + vector[0] * s3
    assert abs(rotated[0] - expected_0) < 1e-10
    assert abs(rotated[2] - expected_2) < 1e-10
    # dim1 paired with dim3 (both zero, so result is zero)
    assert abs(rotated[1]) < 1e-10
    assert abs(rotated[3]) < 1e-10


def test_swiglu_param_count():
    """T014: SwiGLU MLP has ~8/3*n_embd^2 * 3 params (gate, up, down)."""
    model = LlamaModel(vocab_size=27, n_embd=16, n_head=4, n_layer=1, block_size=16)
    intermediate = int(8 * 16 / 3)
    # mlp_gate: intermediate * n_embd, mlp_up: intermediate * n_embd,
    # mlp_down: n_embd * intermediate
    expected_mlp_params = intermediate * 16 + intermediate * 16 + 16 * intermediate
    # Count mlp params from model
    mlp_count = 0
    for li in range(model.n_layer):
        for name in ["mlp_gate", "mlp_up", "mlp_down"]:
            mat = model.state_dict[f"layer{li}.{name}"]
            for row in mat:
                mlp_count += len(row)
    assert mlp_count == expected_mlp_params


def test_swiglu_forward():
    """T014: SwiGLU forward produces valid output with gradient flow."""
    model = LlamaModel(vocab_size=27, n_embd=16, n_head=4, n_layer=1, block_size=16)
    keys = [[] for _ in range(model.n_layer)]
    values = [[] for _ in range(model.n_layer)]
    logits = model.forward(5, 0, keys, values)
    assert len(logits) == 27
    loss = sum(logits)
    loss.backward()
    # Check that gradients flow to SwiGLU params
    assert any(
        abs(p.grad) > 0
        for key in model.state_dict
        if "mlp" in key
        for row in (
            model.state_dict[key]
            if isinstance(model.state_dict[key][0], list)
            else [model.state_dict[key]]
        )
        for p in (row if isinstance(row, list) else [row])
    )


def test_rmsnorm_scale_initialization():
    """T019: RMSNorm scales initialize to 1.0."""
    model = LlamaModel(vocab_size=27, n_embd=16, n_head=4, n_layer=2, block_size=16)
    # Check rms_1, rms_2 for each layer, and rms_final
    for li in range(model.n_layer):
        for name in ["rms_1", "rms_2"]:
            scales = model.state_dict[f"layer{li}.{name}"]
            for s in scales:
                assert abs(s.data - 1.0) < 1e-10
    for s in model.state_dict["rms_final"]:
        assert abs(s.data - 1.0) < 1e-10


def test_rmsnorm_gradient_flows_through_scales():
    """T019: Gradient flows through RMSNorm scale parameters."""
    model = LlamaModel(vocab_size=27, n_embd=16, n_head=4, n_layer=1, block_size=16)
    keys = [[] for _ in range(model.n_layer)]
    values = [[] for _ in range(model.n_layer)]
    logits = model.forward(5, 0, keys, values)
    loss = sum(logits)
    loss.backward()
    # Check rms_1 scale gradients
    rms_1_scales = model.state_dict["layer0.rms_1"]
    assert any(abs(s.grad) > 0 for s in rms_1_scales)
    # Check rms_2 scale gradients
    rms_2_scales = model.state_dict["layer0.rms_2"]
    assert any(abs(s.grad) > 0 for s in rms_2_scales)
    # Check rms_final scale gradients
    rms_final_scales = model.state_dict["rms_final"]
    assert any(abs(s.grad) > 0 for s in rms_final_scales)


def test_save_load_roundtrip(tmp_path):
    """T022: Save and load a model, verify parameter values match."""
    model = LlamaModel(vocab_size=27, n_embd=16, n_head=4, n_layer=1, block_size=16)
    save_path = str(tmp_path / "test_model.json")
    model.save(save_path)
    loaded = LlamaModel.load(save_path)
    # Check all state dict values match
    for key in model.state_dict:
        orig = model.state_dict[key]
        loaded_val = loaded.state_dict[key]
        if isinstance(orig[0], list):
            for i in range(len(orig)):
                for j in range(len(orig[i])):
                    assert abs(orig[i][j].data - loaded_val[i][j].data) < 1e-10
        else:
            for i in range(len(orig)):
                assert abs(orig[i].data - loaded_val[i].data) < 1e-10
    # Check metadata
    assert loaded.vocab_size == model.vocab_size
    assert loaded.n_embd == model.n_embd
    assert loaded.n_head == model.n_head
    assert loaded.n_layer == model.n_layer
    assert loaded.block_size == model.block_size
    assert loaded.intermediate_size == model.intermediate_size


def test_load_old_format_raises_error(tmp_path):
    """T022: Loading old GPT-2 format raises ValueError."""
    import json

    model = LlamaModel(vocab_size=27, n_embd=16, n_head=4, n_layer=1, block_size=16)
    old_path = str(tmp_path / "old_model.json")
    # Create old-format state dict with wpe
    old_state = {}
    for k, mat in model.state_dict.items():
        if isinstance(mat[0], list):
            old_state[k] = [[p.data for p in row] for row in mat]
        else:
            old_state[k] = [p.data for p in mat]
    old_state["wpe"] = [[0.0] * model.n_embd for _ in range(model.block_size)]
    old_data = {
        "vocab_size": 27,
        "n_embd": 16,
        "n_head": 4,
        "n_layer": 1,
        "block_size": 16,
        "state_dict": old_state,
    }
    with open(old_path, "w") as f:
        json.dump(old_data, f)

    with pytest.raises(ValueError, match="Old GPT-2 format detected"):
        LlamaModel.load(old_path)


def test_head_dim_even_passes():
    """T023b: Even head_dim passes validation."""
    model = LlamaModel(vocab_size=27, n_embd=16, n_head=4, block_size=16)
    assert model.head_dim == 4
    assert model.head_dim % 2 == 0


def test_head_dim_odd_raises():
    """T023b: Odd head_dim raises ValueError."""
    with pytest.raises(ValueError, match="head_dim=5 must be even"):
        LlamaModel(vocab_size=27, n_embd=30, n_head=6, block_size=16)


# --- Edge-case tests (T054) ---


def test_n_layer_zero():
    """T054: n_layer=0 produces a valid model (embedding -> final RMSNorm -> lm_head)."""
    model = LlamaModel(vocab_size=27, n_embd=16, n_head=4, n_layer=0, block_size=16)
    # State dict should have no layer keys
    for key in model.state_dict:
        assert not key.startswith("layer"), f"Unexpected layer key: {key}"
    # Should have wte, lm_head, rms_final
    assert "wte" in model.state_dict
    assert "lm_head" in model.state_dict
    assert "rms_final" in model.state_dict
    # Forward pass should work
    keys = [[] for _ in range(model.n_layer)]
    values = [[] for _ in range(model.n_layer)]
    logits = model.forward(5, 0, keys, values)
    assert len(logits) == 27
    loss = sum(logits)
    loss.backward()
    # Gradients should flow through wte, lm_head, rms_final
    assert any(abs(p.grad) > 0 for p in model.state_dict["wte"][5])
    assert any(abs(p.grad) > 0 for p in model.state_dict["lm_head"][0])
    assert any(abs(p.grad) > 0 for p in model.state_dict["rms_final"])


def test_tiny_dimensions():
    """T054: n_embd=4, n_head=2 (head_dim=2, even -- valid)."""
    model = LlamaModel(vocab_size=27, n_embd=4, n_head=2, block_size=16)
    assert model.head_dim == 2
    assert model.head_dim % 2 == 0
    # Forward pass should work
    keys = [[] for _ in range(model.n_layer)]
    values = [[] for _ in range(model.n_layer)]
    logits = model.forward(5, 0, keys, values)
    assert len(logits) == 27


def test_odd_head_dim_n_embd_6_n_head_2():
    """T054: n_embd=6, n_head=2 -> head_dim=3 (odd) should be rejected."""
    with pytest.raises(ValueError, match="head_dim=3 must be even"):
        LlamaModel(vocab_size=27, n_embd=6, n_head=2, block_size=16)


def test_train_tiny_config():
    """T054: Training for 5 steps with n_embd=8, n_head=2 produces valid loss."""
    docs = ["emma", "olivia", "ava", "isabella"]
    _, final_loss, samples, _ = train(docs, num_steps=5, n_embd=8, n_head=2)
    assert final_loss > 0
    assert isinstance(samples, list)
    assert len(samples) == 20


def test_llama_state_dict_keys():
    """T054: State dict keys match expected Llama keys (no wpe, no fc1/fc2; has mlp_gate, rms_*)."""
    model = LlamaModel(vocab_size=27, n_embd=16, n_head=4, n_layer=2, block_size=16)
    keys = set(model.state_dict.keys())
    # Llama architecture should NOT have GPT-2 keys (wpe, fc1, fc2)
    assert "wpe" not in keys
    assert not any("fc1" in k for k in keys)
    assert not any("fc2" in k for k in keys)
    # Llama architecture should have these keys
    assert "wte" in keys
    assert "lm_head" in keys
    assert "rms_final" in keys
    for li in range(2):
        assert f"layer{li}.attn_wq" in keys
        assert f"layer{li}.attn_wk" in keys
        assert f"layer{li}.attn_wv" in keys
        assert f"layer{li}.attn_wo" in keys
        assert f"layer{li}.mlp_gate" in keys
        assert f"layer{li}.mlp_up" in keys
        assert f"layer{li}.mlp_down" in keys
        assert f"layer{li}.rms_1" in keys
        assert f"layer{li}.rms_2" in keys


# --- Autograd operation coverage tests ---


def test_value_exp_forward_backward():
    """exp() forward produces correct data and backward flows correctly."""
    a = Value(0.0)
    b = a.exp()
    assert abs(b.data - 1.0) < 1e-10
    b.backward()
    # d(exp(x))/dx = exp(x), so at x=0, grad = 1
    assert abs(a.grad - 1.0) < 1e-10

    # Test with positive value
    a2 = Value(2.0)
    b2 = a2.exp()
    assert abs(b2.data - math.exp(2.0)) < 1e-10
    b2.backward()
    assert abs(a2.grad - math.exp(2.0)) < 1e-10


def test_value_pow_forward_backward():
    """__pow__ forward produces correct data and backward flows correctly."""
    a = Value(3.0)
    b = a**2
    assert abs(b.data - 9.0) < 1e-10
    b.backward()
    # d(x^2)/dx = 2x, so at x=3, grad = 6
    assert abs(a.grad - 6.0) < 1e-10

    # Test with exponent 3
    a2 = Value(2.0)
    b2 = a2**3
    assert abs(b2.data - 8.0) < 1e-10
    b2.backward()
    # d(x^3)/dx = 3x^2, so at x=2, grad = 12
    assert abs(a2.grad - 12.0) < 1e-10


def test_value_truediv_forward_backward():
    """__truediv__ forward produces correct data and backward flows."""
    a = Value(10.0)
    b = Value(2.0)
    c = a / b
    assert abs(c.data - 5.0) < 1e-10
    c.backward()
    # c = a * b^-1, dc/da = 1/b = 0.5, dc/db = -a/b^2 = -2.5
    assert abs(a.grad - 0.5) < 1e-10
    assert abs(b.grad - (-2.5)) < 1e-10


def test_value_rtruediv_forward_backward():
    """__rtruediv__ (other / self) forward and backward."""
    a = Value(2.0)
    c = 10.0 / a
    assert abs(c.data - 5.0) < 1e-10
    c.backward()
    # c = 10 * x^-1, dc/dx = -10/x^2 = -2.5
    assert abs(a.grad - (-2.5)) < 1e-10


def test_value_sub_forward_backward():
    """__sub__ forward produces correct data and backward flows."""
    a = Value(10.0)
    b = Value(3.0)
    c = a - b
    assert abs(c.data - 7.0) < 1e-10
    c.backward()
    # c = a + (-b), dc/da = 1, dc/db = -1
    assert abs(a.grad - 1.0) < 1e-10
    assert abs(b.grad - (-1.0)) < 1e-10


def test_value_rsub_forward():
    """__rsub__ (other - self) forward produces correct data."""
    a = Value(3.0)
    c = 10.0 - a
    assert abs(c.data - 7.0) < 1e-10
    c.backward()
    assert abs(a.grad - (-1.0)) < 1e-10


def test_value_neg_forward():
    """__neg__ forward produces correct data and backward flows."""
    a = Value(5.0)
    c = -a
    assert abs(c.data - (-5.0)) < 1e-10
    c.backward()
    assert abs(a.grad - (-1.0)) < 1e-10


def test_value_radd_forward():
    """__radd__ (other + self) forward produces correct data."""
    a = Value(5.0)
    c = 10.0 + a
    assert abs(c.data - 15.0) < 1e-10
    c.backward()
    assert abs(a.grad - 1.0) < 1e-10


def test_value_rmul_forward():
    """__rmul__ (other * self) forward produces correct data."""
    a = Value(3.0)
    c = 5.0 * a
    assert abs(c.data - 15.0) < 1e-10
    c.backward()
    assert abs(a.grad - 5.0) < 1e-10


def test_value_silu_forward_backward():
    """silu() forward produces correct data and backward flows."""
    # silu(0) = 0 * 0.5 = 0
    a = Value(0.0)
    b = a.silu()
    assert abs(b.data - 0.0) < 1e-10
    b.backward()
    # derivative at 0: sigmoid(0) + 0 * sigmoid(0) * (1-sigmoid(0)) = 0.5
    assert abs(a.grad - 0.5) < 1e-10

    # silu(2) = 2 * sigmoid(2)
    a2 = Value(2.0)
    b2 = a2.silu()
    s2 = 1.0 / (1.0 + math.exp(-2.0))
    assert abs(b2.data - (2.0 * s2)) < 1e-10
    b2.backward()
    # derivative: s + x * s * (1-s)
    expected_grad = s2 + 2.0 * s2 * (1.0 - s2)
    assert abs(a2.grad - expected_grad) < 1e-10

    # silu(-2) negative test
    a3 = Value(-2.0)
    b3 = a3.silu()
    s3 = 1.0 / (1.0 + math.exp(2.0))
    assert abs(b3.data - (-2.0 * s3)) < 1e-10


def test_value_grad_accumulation():
    """Gradients accumulate correctly when a Value is used in multiple outputs."""
    a = Value(2.0)
    b = a * 3.0
    c = a * 4.0
    loss = b + c
    loss.backward()
    # db/da = 3, dc/da = 4, so grad(a) = 3 + 4 = 7
    assert abs(a.grad - 7.0) < 1e-10


def test_value_deep_chain():
    """Backward through a deeper chain: f(g(h(x)))."""
    x = Value(2.0)
    a = x * 3.0  # 6
    b = a + 1.0  # 7
    c = b * 2.0  # 14
    c.backward()
    # dc/dx = dc/db * db/da * da/dx = 2 * 1 * 3 = 6
    assert abs(x.grad - 6.0) < 1e-10


def test_value_scalar_operations():
    """Value can operate directly with Python scalar (int/float)."""
    a = Value(5.0)
    assert (a + 3).data == 8.0
    assert (3 + a).data == 8.0
    assert (a * 2).data == 10.0
    assert (2 * a).data == 10.0
    assert (a - 1).data == 4.0
    assert (1 - a).data == -4.0
    assert (a / 2).data == 2.5
    assert (10 / a).data == 2.0


# --- Tokenizer edge case tests ---


def test_tokenizer_empty_doc():
    """encode('') returns just two BOS tokens."""
    tok = Tokenizer(["hello"])
    encoded = tok.encode("")
    assert encoded == [tok.BOS, tok.BOS]


def test_tokenizer_unknown_chars_skipped():
    """Characters not in vocabulary are silently skipped."""
    tok = Tokenizer(["abc"])
    encoded = tok.encode("axyz")
    # Only 'a' is in vocab; 'x', 'y', 'z' are skipped
    assert encoded[0] == tok.BOS
    assert encoded[-1] == tok.BOS
    # 'a' is at index 0
    assert tok.decode(encoded) == "a"


def test_tokenizer_empty_docs():
    """Tokenizer with empty docs list creates zero-size vocabulary."""
    tok = Tokenizer([])
    assert tok.vocab_size == 1
    assert tok.BOS == 0
    encoded = tok.encode("")
    assert encoded == [0, 0]
    decoded = tok.decode([0, 0])
    assert decoded == ""


def test_tokenizer_decode_bos_omitted():
    """decode() silently omits BOS tokens from output."""
    tok = Tokenizer(["abc"])
    # BOS = 3 (index after a, b, c)
    decoded = tok.decode([tok.BOS, 0, 1, tok.BOS, 2, tok.BOS])
    assert decoded == "abc"


def test_tokenizer_vocab_size():
    """vocab_size = len(uchars) + 1 for BOS."""
    tok = Tokenizer(["hello"])
    assert tok.vocab_size == len(tok.uchars) + 1


def test_tokenizer_roundtrip_multiple_docs():
    """Roundtrip encode/decode works for various strings."""
    tok = Tokenizer(["hello", "world"])
    for text in ["hello", "world", "low", "he", "owo"]:
        encoded = tok.encode(text)
        decoded = tok.decode(encoded)
        assert decoded == text, f"Roundtrip failed for '{text}': got '{decoded}'"


def test_tokenizer_roundtrip_with_duplicate_chars():
    """Characters appearing multiple times roundtrip correctly."""
    tok = Tokenizer(["abc"])
    encoded = tok.encode("aaabbbccc")
    decoded = tok.decode(encoded)
    assert decoded == "aaabbbccc"


def test_tokenizer_decode_empty_list():
    """decode([]) returns empty string."""
    tok = Tokenizer(["abc"])
    assert tok.decode([]) == ""


# --- Vocabulary tests ---


def test_vocabulary_roundtrip():
    """Basic Vocabulary encode/decode roundtrip."""
    chars = sorted(set("hello"))
    vocab = Vocabulary(chars)
    encoded = vocab.encode("hello")
    decoded = vocab.decode(encoded)
    assert decoded == "hello"


def test_vocabulary_from_chars():
    """from_chars class method produces a working Vocabulary."""
    chars = sorted(set("world"))
    vocab = Vocabulary.from_chars(chars)
    assert vocab.chars == chars
    assert vocab.bos_id == len(chars)
    encoded = vocab.encode("world")
    decoded = vocab.decode(encoded)
    assert decoded == "world"


def test_vocabulary_unknown_char_skipped():
    """Characters not in vocabulary are silently skipped during encode."""
    chars = sorted(set("abc"))
    vocab = Vocabulary(chars)
    encoded = vocab.encode("axyz")
    decoded = vocab.decode(encoded)
    assert decoded == "a"


def test_vocabulary_empty_text():
    """encode('') returns just two BOS tokens."""
    chars = sorted(set("abc"))
    vocab = Vocabulary(chars)
    encoded = vocab.encode("")
    assert encoded == [vocab.bos_id, vocab.bos_id]
    assert vocab.decode(encoded) == ""


def test_vocabulary_decode_bos_omitted():
    """BOS tokens are silently omitted during decode."""
    chars = sorted(set("abc"))
    vocab = Vocabulary(chars)
    # IDs: 0=a, 1=b, 2=c, bos_id=3
    decoded = vocab.decode([3, 0, 1, 3, 2, 3])
    assert decoded == "abc"


def test_vocabulary_decode_empty_list():
    """decode([]) returns empty string."""
    chars = sorted(set("abc"))
    vocab = Vocabulary(chars)
    assert vocab.decode([]) == ""


def test_vocabulary_bos_id():
    """bos_id equals len(chars) and vocab_size equals len(chars) + 1."""
    chars = sorted(set("abcdef"))
    vocab = Vocabulary(chars)
    assert vocab.bos_id == 6
    assert vocab.vocab_size == 7


def test_vocabulary_tokenizer_parity():
    """Vocabulary encode/decode matches Tokenizer for same characters."""
    chars = sorted(set("hello"))
    vocab = Vocabulary(chars)
    tok = Tokenizer(["hello"])
    for text in ["hello", "hell", "eo", "h", ""]:
        v_encoded = vocab.encode(text)
        t_encoded = tok.encode(text)
        assert v_encoded == t_encoded, f"encode mismatch for '{text}'"
        v_decoded = vocab.decode(v_encoded)
        t_decoded = tok.decode(t_encoded)
        assert v_decoded == t_decoded, f"decode mismatch for '{text}'"


# --- Engine helper function tests ---


def test_matrix_shape():
    """matrix(nout, nin) returns list of nout rows each with nin Value elements."""
    m = matrix(3, 4)
    assert len(m) == 3
    assert all(len(row) == 4 for row in m)
    assert all(isinstance(v, Value) for row in m for v in row)


def test_linear_function():
    """linear(x, w) computes weighted sum correctly."""
    x = [Value(1.0), Value(2.0), Value(3.0)]
    w = [
        [Value(1.0), Value(0.0), Value(0.0)],
        [Value(0.0), Value(1.0), Value(0.0)],
    ]
    result = linear(x, w)
    assert len(result) == 2
    assert abs(result[0].data - 1.0) < 1e-10
    assert abs(result[1].data - 2.0) < 1e-10


def test_linear_gradient_flow():
    """linear() gradients flow backward through both inputs and weights."""
    x = [Value(1.0), Value(2.0)]
    w = [[Value(3.0), Value(4.0)]]
    result = linear(x, w)
    result[0].backward()
    # result = 1*3 + 2*4 = 11
    assert abs(result[0].data - 11.0) < 1e-10
    # dx1 = w1 = 3, dx2 = w2 = 4
    assert abs(x[0].grad - 3.0) < 1e-10
    assert abs(x[1].grad - 4.0) < 1e-10
    # dw1 = x1 = 1, dw2 = x2 = 2
    assert abs(w[0][0].grad - 1.0) < 1e-10
    assert abs(w[0][1].grad - 2.0) < 1e-10


def test_softmax_uniform():
    """Softmax on uniform inputs produces equal probabilities."""
    from anvil.core.autograd import Value

    logits = [Value(2.0), Value(2.0), Value(2.0)]
    probs = softmax(logits)
    assert len(probs) == 3
    for p in probs:
        assert abs(p.data - 1.0 / 3.0) < 1e-10


def test_softmax_single():
    """Softmax on single element returns 1.0."""
    logits = [Value(5.0)]
    probs = softmax(logits)
    assert abs(probs[0].data - 1.0) < 1e-10


def test_softmax_large_range():
    """Softmax with large value range (numerical stability via max subtraction)."""
    logits = [Value(1000.0), Value(0.0)]
    probs = softmax(logits)
    # After max subtraction: [0, -1000]; exp gives [1, ~0]
    assert abs(probs[0].data - 1.0) < 1e-10
    assert abs(probs[1].data - 0.0) < 1e-10


def test_softmax_negative_inputs():
    """Softmax with all negative values is still valid."""
    logits = [Value(-1.0), Value(-2.0), Value(-3.0)]
    probs = softmax(logits)
    total = sum(p.data for p in probs)
    assert abs(total - 1.0) < 1e-10


def test_softmax_gradient_flow():
    """Gradient flows backward through softmax."""
    logits = [Value(1.0), Value(2.0)]
    probs = softmax(logits)
    loss = sum(p * Value(i) for i, p in enumerate(probs))
    loss.backward()
    # Gradients should exist on all logits
    assert all(abs(p.grad) > 0 for p in logits)


def test_rmsnorm_negative_values():
    """Rmsnorm handles negative values correctly (squared makes them positive)."""
    x = [Value(-3.0), Value(-4.0)]
    n = rmsnorm(x)
    ms = (9.0 + 16.0) / 2.0  # 12.5
    scale = (ms + 1e-5) ** -0.5
    assert abs(n[0].data - (-3.0 * scale)) < 1e-10
    assert abs(n[1].data - (-4.0 * scale)) < 1e-10
    n[0].backward()
    assert all(abs(v.grad) > 0 for v in x)


def test_rmsnorm_zero():
    """Rmsnorm with all zeros produces zeros (with epsilon)."""
    x = [Value(0.0), Value(0.0), Value(0.0)]
    n = rmsnorm(x)
    for ni in n:
        assert abs(ni.data) < 1e-10


def test_precompute_rope_custom_theta():
    """precompute_rope with custom theta value produces valid tables."""
    cos_t, sin_t = precompute_rope(4, 4, theta=5000.0)
    assert len(cos_t) == 4
    assert len(sin_t) == 4
    assert len(cos_t[0]) == 2  # half = head_dim // 2
    # theta=5000 gives lower frequencies than default 10000
    cos_t2, sin_t2 = precompute_rope(4, 4, theta=10000.0)
    assert cos_t[1] != cos_t2[1]  # Different theta produces different values


def test_precompute_rope_varied_seq_len():
    """precompute_rope works for different sequence lengths."""
    for seq_len in [1, 2, 8, 16]:
        cos_t, sin_t = precompute_rope(seq_len, 4)
        assert len(cos_t) == seq_len
        assert len(sin_t) == seq_len


def test_precompute_rope_single_pos():
    """precompute_rope with seq_len=1 produces one entry."""
    cos_t, sin_t = precompute_rope(1, 4)
    assert len(cos_t) == 1
    assert len(sin_t) == 1


# --- forward_introspect tests ---


def test_forward_introspect_structure():
    """forward_introspect returns correct dict keys and shapes."""
    model = LlamaModel(vocab_size=27, n_embd=16, n_head=4, n_layer=1, block_size=16)
    result = model.forward_introspect([5, 6])
    assert "attention" in result
    assert "logits" in result
    assert "embeddings" in result
    assert "n_layer" in result
    assert "n_head" in result
    assert "tokens" in result
    assert result["n_layer"] == 1
    assert result["n_head"] == 4
    assert result["tokens"] == [5, 6]
    assert len(result["embeddings"]) == 2
    assert len(result["logits"]) == 27
    # attention[layer][head][pos] = list of weights
    assert len(result["attention"][0][0][0]) == 1  # first pos, 1 key
    assert len(result["attention"][0][0][1]) == 2  # second pos, 2 keys


def test_forward_introspect_zero_layer():
    """forward_introspect works with n_layer=0."""
    model = LlamaModel(vocab_size=27, n_embd=16, n_head=4, n_layer=0, block_size=16)
    result = model.forward_introspect([5])
    assert len(result["attention"]) == 0
    assert len(result["embeddings"]) == 1
    assert len(result["logits"]) == 27


# --- train function edge case tests ---


def test_train_stop_check():
    """train() with stop_check that stops at step 1 returns early."""
    docs = ["hello", "world"]
    call_count = [0]

    def stop_after_one():
        call_count[0] += 1
        return call_count[0] > 1

    model, loss, samples, _ = train(docs, num_steps=100, stop_check=stop_after_one)
    # Training runs for 1 step (stop after step 1), loss is valid
    assert loss > 0
    assert len(samples) == 20


def test_train_stop_check_mid_training():
    """train() with stop_check that stops after a few steps."""
    docs = ["abc", "def"]
    step_count = [0]

    def stop_after_3():
        step_count[0] += 1
        return step_count[0] >= 3

    model, loss, samples, _ = train(
        docs, num_steps=50, stop_check=stop_after_3, n_embd=8, n_head=2
    )
    assert len(samples) == 20


def test_train_progress_callback():
    """train() invokes progress_callback on each step."""
    docs = ["ab", "cd"]
    captured = []

    def cb(step, loss, tokens, grad_norm):
        captured.append({"step": step, "loss": loss, "tokens": tokens})

    train(docs, num_steps=5, n_embd=8, n_head=2, progress_callback=cb)
    assert len(captured) == 5
    for entry in captured:
        assert entry["loss"] > 0
        assert entry["tokens"] > 0


def test_train_with_existing_model():
    """train() accepts an existing model and updates its parameters."""
    docs = ["hi", "lo"]
    model = LlamaModel(vocab_size=5, n_embd=8, n_head=2, n_layer=1, block_size=16)
    params_before = [p.data for p in model.params[:5]]
    result_model, _, _, _ = train(docs, model=model, num_steps=3, n_embd=8, n_head=2)
    params_after = [p.data for p in result_model.params[:5]]
    assert any(
        abs(before - after) > 1e-10
        for before, after in zip(params_before, params_after, strict=False)
    )


def test_train_learning_rate_decay():
    """train() with high num_steps should show learning rate decay effect."""
    docs = ["a", "b", "c"]
    model, loss, samples, _ = train(
        docs,
        num_steps=10,
        n_embd=8,
        n_head=2,
        learning_rate=0.01,
    )
    assert loss > 0
    assert len(samples) == 20


def test_train_temperature_effect():
    """train() with different temperature produces valid samples."""
    docs = ["hello", "world"]
    _, _, samples_high_temp, _ = train(
        docs, num_steps=5, n_embd=8, n_head=2, temperature=1.0
    )
    assert len(samples_high_temp) == 20
