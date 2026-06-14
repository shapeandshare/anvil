"""train3: Single-head causal self-attention with learned position embeddings,
RMSNorm, residual connections, and a single transformer block."""

import random

random.seed(42)

from microgpt.core.autograd import Value
from microgpt.core.engine import linear, matrix, rmsnorm, softmax

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

# --- parameters ---
wte = matrix(vocab_size, n_embd)
wpe = matrix(block_size, n_embd)
attn_wq = matrix(n_embd, n_embd)
attn_wk = matrix(n_embd, n_embd)
attn_wv = matrix(n_embd, n_embd)
attn_wo = matrix(n_embd, n_embd)
mlp_fc1 = matrix(4 * n_embd, n_embd)
mlp_fc2 = matrix(n_embd, 4 * n_embd)
lm_head = matrix(vocab_size, n_embd)

all_mats = [
    wte, wpe,
    attn_wq, attn_wk, attn_wv, attn_wo,
    mlp_fc1, mlp_fc2,
    lm_head,
]
params: list[Value] = [p for mat in all_mats for row in mat for p in row]


def forward(
    token_id: int, pos_id: int, keys: list[list[Value]], values: list[list[Value]]
) -> list[Value]:
    tok_emb = wte[token_id]
    pos_emb = wpe[pos_id]
    x = [t + p for t, p in zip(tok_emb, pos_emb)]
    x = rmsnorm(x)

    # single-head causal self-attention
    x_res = x
    q = linear(x, attn_wq)
    k = linear(x, attn_wk)
    v = linear(x, attn_wv)
    keys.append(k)
    values.append(v)

    attn_logits = [
        sum(q[j] * keys[t][j] for j in range(n_embd)) / (n_embd**0.5)
        for t in range(len(keys))
    ]
    attn_weights = softmax(attn_logits)
    attn_out = [
        sum(attn_weights[t] * values[t][j] for t in range(len(values)))
        for j in range(n_embd)
    ]
    x = linear(attn_out, attn_wo)
    x = [a + b for a, b in zip(x, x_res)]

    # residual MLP
    x_res = x
    x = rmsnorm(x)
    x = linear(x, mlp_fc1)
    x = [xi.relu() for xi in x]
    x = linear(x, mlp_fc2)
    x = [a + b for a, b in zip(x, x_res)]

    logits = linear(x, lm_head)
    return logits


# --- training ---
print("Training single-head transformer with SGD...")
for step in range(100):
    doc = docs[step % len(docs)]
    tokens = [BOS] + [uchars.index(ch) for ch in doc] + [BOS]
    n = min(block_size, len(tokens) - 1)
    keys: list[list[Value]] = []
    values: list[list[Value]] = []
    losses: list[Value] = []
    for pos_id in range(n):
        token_id = tokens[pos_id]
        target_id = tokens[pos_id + 1]
        logits = forward(token_id, pos_id, keys, values)
        probs = softmax(logits)
        loss_t = -probs[target_id].log()
        losses.append(loss_t)
    loss = (1.0 / n) * sum(losses)
    loss.backward()

    for p in params:
        p.data -= lr * p.grad
        p.grad = 0.0

    print(f"step {step:3d}, loss {loss.data:.4f}")