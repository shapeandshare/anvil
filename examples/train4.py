# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""train4: Single transformer block with pre-RMSNorm, multi-head RoPE attention,
and SwiGLU MLP. Full block:
  pre-attn RMSNorm → RoPE attention → residual
  → pre-MLP RMSNorm → SwiGLU MLP → residual.
No learned position embeddings (wpe) — RoPE encodes position."""

import random

random.seed(42)

from anvil.core.autograd import Value
from anvil.core.engine import (
    apply_rope,
    linear,
    matrix,
    precompute_rope,
    rmsnorm,
    softmax,
)

# --- data ---
docs = [l.strip() for l in open("input.txt") if l.strip()]
uchars = sorted(set("".join(docs)))
V = len(uchars)
BOS = V
vocab_size = V + 1

# --- hyperparameters ---
n_embd = 16
block_size = 16
n_head = 4
head_dim = n_embd // n_head  # 4
intermediate_size = int(8 * n_embd / 3)  # ~42 for n_embd=16
lr = 0.01

# --- parameters (no wpe, no embedding-level norm) ---
wte = matrix(vocab_size, n_embd)
attn_wq = matrix(n_embd, n_embd)
attn_wk = matrix(n_embd, n_embd)
attn_wv = matrix(n_embd, n_embd)
attn_wo = matrix(n_embd, n_embd)
mlp_gate = matrix(intermediate_size, n_embd)
mlp_up = matrix(intermediate_size, n_embd)
mlp_down = matrix(n_embd, intermediate_size)
rms_1 = [Value(1.0) for _ in range(n_embd)]  # pre-attention norm scale
rms_2 = [Value(1.0) for _ in range(n_embd)]  # pre-MLP norm scale
lm_head = matrix(vocab_size, n_embd)

all_mats = [
    wte,
    attn_wq,
    attn_wk,
    attn_wv,
    attn_wo,
    mlp_gate,
    mlp_up,
    mlp_down,
    lm_head,
]
params: list[Value] = (
    [p for mat in all_mats for row in mat for p in row] + rms_1 + rms_2
)

# Precompute RoPE tables (half-split, per-head dimension)
cos_table, sin_table = precompute_rope(block_size, head_dim)


def forward(
    token_id: int,
    pos_id: int,
    keys_cache: list[list[Value]],
    values_cache: list[list[Value]],
) -> list[Value]:
    """Full transformer block forward pass."""
    x = wte[token_id]

    # ── Pre-attention RMSNorm + multi-head RoPE attention ──
    x_residual = x
    r = [s * xi for s, xi in zip(rms_1, rmsnorm(x))]

    q = linear(r, attn_wq)
    k = linear(r, attn_wk)
    v = linear(r, attn_wv)

    # Apply RoPE per head (Q and K only, not V)
    q_rotated: list[Value] = []
    k_rotated: list[Value] = []
    for h in range(n_head):
        hs = h * head_dim
        q_rotated.extend(
            apply_rope(q[hs : hs + head_dim], pos_id, cos_table, sin_table)
        )
        k_rotated.extend(
            apply_rope(k[hs : hs + head_dim], pos_id, cos_table, sin_table)
        )
    q = q_rotated
    k = k_rotated

    keys_cache.append(k)
    values_cache.append(v)

    # Multi-head causal attention
    x_attn: list[Value] = []
    for h in range(n_head):
        hs = h * head_dim
        q_h = q[hs : hs + head_dim]
        k_h = [ki[hs : hs + head_dim] for ki in keys_cache]
        v_h = [vi[hs : hs + head_dim] for vi in values_cache]

        attn_logits = [
            sum(q_h[j] * k_h[t][j] for j in range(head_dim)) / (head_dim**0.5)
            for t in range(len(k_h))
        ]
        attn_weights = softmax(attn_logits)
        head_out = [
            sum(attn_weights[t] * v_h[t][j] for t in range(len(v_h)))
            for j in range(head_dim)
        ]
        x_attn.extend(head_out)

    x = linear(x_attn, attn_wo)
    x = [a + b for a, b in zip(x, x_residual)]

    # ── Pre-MLP RMSNorm + SwiGLU MLP ──
    x_residual = x
    r2 = [s * xi for s, xi in zip(rms_2, rmsnorm(x))]

    # SwiGLU: gate = SiLU(linear(x)), up = linear(x), combined = gate * up
    gate = linear(r2, mlp_gate)
    gate = [gi.silu() for gi in gate]
    up = linear(r2, mlp_up)
    combined = [g * u for g, u in zip(gate, up)]
    x = linear(combined, mlp_down)
    x = [a + b for a, b in zip(x, x_residual)]

    logits = linear(x, lm_head)
    return logits


# --- training ---
print("Training single Llama block (RMSNorm + RoPE attn + SwiGLU)...")
for step in range(200):
    doc = docs[step % len(docs)]
    tokens = [BOS] + [uchars.index(ch) for ch in doc] + [BOS]
    n = min(block_size, len(tokens) - 1)
    keys_cache: list[list[Value]] = []
    values_cache: list[list[Value]] = []
    losses: list[Value] = []
    for pos_id in range(n):
        token_id = tokens[pos_id]
        target_id = tokens[pos_id + 1]
        logits = forward(token_id, pos_id, keys_cache, values_cache)
        probs = softmax(logits)
        loss_t = -probs[target_id].log()
        losses.append(loss_t)
    loss = (1.0 / n) * sum(losses)
    loss.backward()

    for p in params:
        p.data -= lr * p.grad
        p.grad = 0.0

    if step == 0 or (step + 1) % 50 == 0:
        print(f"step {step:3d}, loss {loss.data:.4f}")
