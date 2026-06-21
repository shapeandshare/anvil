# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""train1: 2-layer MLP (input -> hidden+ReLU -> output).
Manual numerical gradients (finite differences) and analytic gradients (chain rule).
Verify they match within 1e-4, then train with SGD on character prediction."""

import math
import random

random.seed(42)

# --- data: next-character prediction on names dataset ---
docs = [l.strip() for l in open("examples/input.txt") if l.strip()]
uchars = sorted(set("".join(docs)))
V = len(uchars)  # vocabulary size (26 lowercase letters)
H = 16  # hidden layer size

# Build training pairs: (char_idx, next_char_idx)
X: list[int] = []
Y: list[int] = []
for doc in docs:
    for i in range(len(doc) - 1):
        X.append(uchars.index(doc[i]))
        Y.append(uchars.index(doc[i + 1]))
# Use a subset for speed (pure Python training loops are slow)
X = X[:500]
Y = Y[:500]


# --- parameters ---
def init_param() -> float:
    return random.gauss(0, 0.08)


W1 = [[init_param() for _ in range(V)] for _ in range(H)]  # H x V
b1 = [0.0] * H
W2 = [[init_param() for _ in range(H)] for _ in range(V)]  # V x H
b2 = [0.0] * V


# --- forward pass ---
def forward(x_idx: int) -> tuple[list[float], tuple]:
    """Return (probs, cache) where cache saves intermediates for backward."""
    x_onehot = [0.0] * V
    x_onehot[x_idx] = 1.0
    # hidden
    z1 = [sum(W1[i][j] * x_onehot[j] for j in range(V)) + b1[i] for i in range(H)]
    h = [max(0.0, z) for z in z1]  # ReLU
    # output
    z2 = [sum(W2[i][j] * h[j] for j in range(H)) + b2[i] for i in range(V)]
    # softmax
    mz = max(z2)
    exps = [math.exp(z - mz) for z in z2]
    total = sum(exps)
    probs = [e / total for e in exps]
    return probs, (x_onehot, z1, h, z2)


def loss_fn(probs: list[float], target: int) -> float:
    return -math.log(max(probs[target], 1e-15))


# --- analytic gradients (chain rule by hand) ---
def analytic_backward(probs: list[float], target: int, cache: tuple) -> tuple:
    """Return (dW1, db1, dW2, db2) computed analytically."""
    x_onehot, z1, h, z2 = cache

    dW1 = [[0.0] * V for _ in range(H)]
    db1 = [0.0] * H
    dW2 = [[0.0] * H for _ in range(V)]
    db2 = [0.0] * V

    # dL/dz2 = softmax - one_hot(target)
    dz2 = [probs[i] - (1.0 if i == target else 0.0) for i in range(V)]

    # dL/dW2[i,j] = dz2[i] * h[j],  dL/db2[i] = dz2[i]
    for i in range(V):
        db2[i] = dz2[i]
        for j in range(H):
            dW2[i][j] = dz2[i] * h[j]

    # dL/dh[j] = sum_i(dz2[i] * W2[i][j])
    dh = [sum(dz2[i] * W2[i][j] for i in range(V)) for j in range(H)]

    # dL/dz1 = dh * (z1 > 0)  (ReLU grad)
    dz1 = [dh[i] * (1.0 if z1[i] > 0 else 0.0) for i in range(H)]

    # dL/dW1[i,j] = dz1[i] * x[j],  dL/db1[i] = dz1[i]
    for i in range(H):
        db1[i] = dz1[i]
        for j in range(V):
            dW1[i][j] = dz1[i] * x_onehot[j]

    return dW1, db1, dW2, db2


# --- numerical gradients (finite differences) ---
def numerical_grad(x_idx: int, target: int, eps: float = 1e-5) -> tuple:
    """Return (dW1, db1, dW2, db2) via two-sided finite differences."""
    dW1 = [[0.0] * V for _ in range(H)]
    db1 = [0.0] * H
    dW2 = [[0.0] * H for _ in range(V)]
    db2 = [0.0] * V

    for i in range(H):
        for j in range(V):
            old = W1[i][j]
            W1[i][j] = old + eps
            p, _ = forward(x_idx)
            lp = loss_fn(p, target)
            W1[i][j] = old - eps
            p, _ = forward(x_idx)
            lm = loss_fn(p, target)
            W1[i][j] = old
            dW1[i][j] = (lp - lm) / (2.0 * eps)

    for i in range(H):
        old = b1[i]
        b1[i] = old + eps
        p, _ = forward(x_idx)
        lp = loss_fn(p, target)
        b1[i] = old - eps
        p, _ = forward(x_idx)
        lm = loss_fn(p, target)
        b1[i] = old
        db1[i] = (lp - lm) / (2.0 * eps)

    for i in range(V):
        for j in range(H):
            old = W2[i][j]
            W2[i][j] = old + eps
            p, _ = forward(x_idx)
            lp = loss_fn(p, target)
            W2[i][j] = old - eps
            p, _ = forward(x_idx)
            lm = loss_fn(p, target)
            W2[i][j] = old
            dW2[i][j] = (lp - lm) / (2.0 * eps)

    for i in range(V):
        old = b2[i]
        b2[i] = old + eps
        p, _ = forward(x_idx)
        lp = loss_fn(p, target)
        b2[i] = old - eps
        p, _ = forward(x_idx)
        lm = loss_fn(p, target)
        b2[i] = old
        db2[i] = (lp - lm) / (2.0 * eps)

    return dW1, db1, dW2, db2


# --- verify gradients match ---
print("Verifying analytic vs numerical gradients on one example...")
check_idx = 0
p, cache = forward(X[check_idx])
ana = analytic_backward(p, Y[check_idx], cache)
num = numerical_grad(X[check_idx], Y[check_idx])

max_diff = 0.0
for layer_idx, (a, n) in enumerate(zip(ana, num)):
    for i in range(len(a)):
        if isinstance(a[i], list):
            for j in range(len(a[i])):
                diff = abs(a[i][j] - n[i][j])
                max_diff = max(max_diff, diff)
        else:
            diff = abs(a[i] - n[i])
            max_diff = max(max_diff, diff)

print(f"Max |analytic - numerical| = {max_diff:.6e}")
if max_diff < 1e-4:
    print("✓ Gradients match within 1e-4 tolerance!")
else:
    print("✗ Gradient mismatch exceeds tolerance!")

# --- SGD training ---
lr = 0.1
print("\nTraining with SGD...")
for step in range(100):
    total_loss = 0.0
    for i in range(len(X)):
        probs_i, cache_i = forward(X[i])
        loss_i = loss_fn(probs_i, Y[i])
        total_loss += loss_i

        dW1_i, db1_i, dW2_i, db2_i = analytic_backward(probs_i, Y[i], cache_i)

        # SGD update
        for ii in range(H):
            for jj in range(V):
                W1[ii][jj] -= lr * dW1_i[ii][jj]
            b1[ii] -= lr * db1_i[ii]
        for ii in range(V):
            for jj in range(H):
                W2[ii][jj] -= lr * dW2_i[ii][jj]
            b2[ii] -= lr * db2_i[ii]

    avg_loss = total_loss / len(X)
    print(f"step {step:3d}, loss {avg_loss:.4f}")
