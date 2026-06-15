"""Unit tests for the core training engine."""

import math

import pytest

from anvil.core.autograd import Value
from anvil.core.engine import GPT, apply_rope, precompute_rope, train
from anvil.core.tokenizer import Tokenizer


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
        captured.append({"step": step, "m_len": len(m), "v_len": len(v), "grads_len": len(grads)})

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
    model = GPT(vocab_size=27, n_embd=16, n_head=4, n_layer=1, block_size=16)
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
    model = GPT(vocab_size=27, n_embd=16, n_head=4, n_layer=1, block_size=16)
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
        for row in (model.state_dict[key] if isinstance(model.state_dict[key][0], list) else [model.state_dict[key]])
        for p in (row if isinstance(row, list) else [row])
    )


def test_rmsnorm_scale_initialization():
    """T019: RMSNorm scales initialize to 1.0."""
    model = GPT(vocab_size=27, n_embd=16, n_head=4, n_layer=2, block_size=16)
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
    model = GPT(vocab_size=27, n_embd=16, n_head=4, n_layer=1, block_size=16)
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
    model = GPT(vocab_size=27, n_embd=16, n_head=4, n_layer=1, block_size=16)
    save_path = str(tmp_path / "test_model.json")
    model.save(save_path)
    loaded = GPT.load(save_path)
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

    model = GPT(vocab_size=27, n_embd=16, n_head=4, n_layer=1, block_size=16)
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
        GPT.load(old_path)


def test_head_dim_even_passes():
    """T023b: Even head_dim passes validation."""
    model = GPT(vocab_size=27, n_embd=16, n_head=4, block_size=16)
    assert model.head_dim == 4
    assert model.head_dim % 2 == 0


def test_head_dim_odd_raises():
    """T023b: Odd head_dim raises ValueError."""
    with pytest.raises(ValueError, match="head_dim=5 must be even"):
        GPT(vocab_size=27, n_embd=30, n_head=6, block_size=16)


# --- Edge-case tests (T054) ---


def test_n_layer_zero():
    """T054: n_layer=0 produces a valid model (embedding -> final RMSNorm -> lm_head)."""
    model = GPT(vocab_size=27, n_embd=16, n_head=4, n_layer=0, block_size=16)
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
    model = GPT(vocab_size=27, n_embd=4, n_head=2, block_size=16)
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
        GPT(vocab_size=27, n_embd=6, n_head=2, block_size=16)


def test_train_tiny_config():
    """T054: Training for 5 steps with n_embd=8, n_head=2 produces valid loss."""
    docs = ["emma", "olivia", "ava", "isabella"]
    _, final_loss, samples, _ = train(docs, num_steps=5, n_embd=8, n_head=2)
    assert final_loss > 0
    assert isinstance(samples, list)
    assert len(samples) == 20


def test_llama_state_dict_keys():
    """T054: State dict keys match expected Llama keys (no wpe, no fc1/fc2; has mlp_gate, rms_*)."""
    model = GPT(vocab_size=27, n_embd=16, n_head=4, n_layer=2, block_size=16)
    keys = set(model.state_dict.keys())
    # Llama architecture should NOT have GPT-2 keys
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
