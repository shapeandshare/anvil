"""train3: Single-head causal self-attention with half-split RoPE.
No learned position embeddings — position is encoded via RoPE rotation angles.
No MLP — this script focuses purely on attention."""

import random

random.seed(42)

from anvil.core.autograd import Value
from anvil.core.engine import softmax, linear, matrix, precompute_rope, apply_rope

# --- data ---
docs = [l.strip() for l in open("input.txt") if l.strip()]
uchars = sorted(set("".join(docs)))
V = len(uchars)
BOS = V
vocab_size = V + 1

# --- hyperparameters ---
n_embd = 16
block_size = 16
lr = 0.01

# --- parameters (no wpe, no MLP) ---
wte = matrix(vocab_size, n_embd)
attn_wq = matrix(n_embd, n_embd)
attn_wk = matrix(n_embd, n_embd)
attn_wv = matrix(n_embd, n_embd)
attn_wo = matrix(n_embd, n_embd)
lm_head = matrix(vocab_size, n_embd)

all_mats = [wte, attn_wq, attn_wk, attn_wv, attn_wo, lm_head]
params: list[Value] = [p for mat in all_mats for row in mat for p in row]

# --- Precompute half-split RoPE tables ---
# Half-split convention: pairs dimension i with dimension i + d//2
cos_table, sin_table = precompute_rope(block_size, n_embd)

print("RoPE cos angles (pos 0-3, dim 0-3):")
for pos in range(4):
    print(f"  pos {pos}: {[f'{v:.4f}' for v in cos_table[pos][:4]]}")
print("RoPE sin angles (pos 0-3, dim 0-3):")
for pos in range(4):
    print(f"  pos {pos}: {[f'{v:.4f}' for v in sin_table[pos][:4]]}")


def forward(
    token_id: int, pos_id: int,
    keys_cache: list[list[Value]], values_cache: list[list[Value]],
) -> list[Value]:
    """Token embed → QKV proj → RoPE on Q/K only → causal attn → output proj."""
    x = wte[token_id]  # token embedding only (no wpe — RoPE encodes position)

    # QKV projections
    q = linear(x, attn_wq)
    k = linear(x, attn_wk)
    v = linear(x, attn_wv)

    # Apply half-split RoPE to Q and K — NOT V (value retains absolute position)
    q = apply_rope(q, pos_id, cos_table, sin_table)
    k = apply_rope(k, pos_id, cos_table, sin_table)

    keys_cache.append(k)
    values_cache.append(v)

    # Causal self-attention: each position attends to itself and previous
    d = n_embd ** 0.5
    attn_logits = [
        sum(q[j] * keys_cache[t][j] for j in range(n_embd)) / d
        for t in range(len(keys_cache))
    ]
    attn_weights = softmax(attn_logits)
    attn_out = [
        sum(attn_weights[t] * values_cache[t][j] for t in range(len(values_cache)))
        for j in range(n_embd)
    ]

    x = linear(attn_out, attn_wo)
    logits = linear(x, lm_head)
    return logits


# --- training ---
print("\nTraining single-head self-attention with RoPE (Adam)...")
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