# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""train2: RMSNorm with learned weights — normalization and backprop through it.
Uses Adam optimizer. Introduces rmsnorm() and a learned scale parameter rms_1."""

import random

random.seed(42)

from anvil.core.autograd import Value
from anvil.core.engine import linear, matrix, rmsnorm, softmax

# --- data: next-character prediction on names dataset ---
docs = [l.strip() for l in open("examples/input.txt") if l.strip()]
uchars = sorted(set("".join(docs)))
V = len(uchars)
BOS = V
vocab_size = V + 1

# Build training pairs
X: list[int] = []
Y: list[int] = []
for doc in docs:
    for i in range(len(doc) - 1):
        X.append(uchars.index(doc[i]))
        Y.append(uchars.index(doc[i + 1]))
X = X[:500]
Y = Y[:500]

# --- hyperparameters ---
n_embd = 16
lr = 0.01

# --- parameters ---
wte = matrix(vocab_size, n_embd)
# Learned RMSNorm scale — initialized to 1.0 (identity at start)
rms_1 = [Value(1.0) for _ in range(n_embd)]
lm_head = matrix(vocab_size, n_embd)

all_mats = [wte, lm_head]
params: list[Value] = [p for mat in all_mats for row in mat for p in row] + rms_1


def forward(token_id: int) -> list[Value]:
    """Embed → RMSNorm → learned scale → linear projection → logits."""
    x = wte[token_id]
    # RMSNorm normalizes by root-mean-square, making output unit-variance
    n = rmsnorm(x)
    # Multiply by learned scale (starts at 1.0, learns feature importance)
    scaled = [s * xi for s, xi in zip(rms_1, n)]
    logits = linear(scaled, lm_head)
    return logits


# --- Adam optimizer state ---
m = [0.0] * len(params)
v = [0.0] * len(params)

print("Training RMSNorm with learned scale (Adam)...")
for step in range(200):
    total_loss = 0.0
    for i in range(len(X)):
        logits = forward(X[i])
        probs = softmax(logits)
        loss_t = -probs[Y[i]].log()
        total_loss += loss_t.data
        loss_t.backward()

        lr_t = lr * (1 - step / 200)
        for j, p in enumerate(params):
            m[j] = 0.85 * m[j] + (1 - 0.85) * p.grad
            v[j] = 0.99 * v[j] + (1 - 0.99) * p.grad**2
            m_hat = m[j] / (1 - 0.85 ** (step + 1))
            v_hat = v[j] / (1 - 0.99 ** (step + 1))
            p.data -= lr_t * m_hat / (v_hat**0.5 + 1e-8)
            p.grad = 0.0

    avg_loss = total_loss / len(X)
    if step == 0 or (step + 1) % 50 == 0:
        rms_str = ", ".join(f"{p.data:.3f}" for p in rms_1[:4])
        print(f"step {step:3d}, loss {avg_loss:.4f}, rms_1[:4] = [{rms_str}, ...]")
