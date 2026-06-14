"""train4: Multi-head GPT (n_head=4, n_embd=16) with learned embeddings
(wte, wpe), RMSNorm, multi-head attention, residual MLP, single layer."""

import random

random.seed(42)

from microgpt.core.autograd import Value
from microgpt.core.engine import GPT, softmax

# --- data ---
docs = [l.strip() for l in open("input.txt") if l.strip()]
uchars = sorted(set("".join(docs)))
BOS = len(uchars)
vocab_size = len(uchars) + 1

# --- hyperparameters ---
n_embd = 16
n_head = 4
block_size = 16
lr = 0.01

# --- model ---
model = GPT(
    vocab_size=vocab_size,
    n_embd=n_embd,
    n_head=n_head,
    n_layer=1,
    block_size=block_size,
)

# --- training ---
print("Training multi-head GPT with SGD...")
for step in range(100):
    doc = docs[step % len(docs)]
    tokens = [BOS] + [uchars.index(ch) for ch in doc] + [BOS]
    n = min(block_size, len(tokens) - 1)
    keys = [[] for _ in range(model.n_layer)]
    values = [[] for _ in range(model.n_layer)]
    losses: list[Value] = []
    for pos_id in range(n):
        token_id = tokens[pos_id]
        target_id = tokens[pos_id + 1]
        logits = model.forward(token_id, pos_id, keys, values)
        probs = softmax(logits)
        loss_t = -probs[target_id].log()
        losses.append(loss_t)
    loss = (1.0 / n) * sum(losses)
    loss.backward()

    for p in model.params:
        p.data -= lr * p.grad
        p.grad = 0.0

    print(f"step {step:3d}, loss {loss.data:.4f}")