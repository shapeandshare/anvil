# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""From-scratch Llama-style transformer engine with zero external deps.

Provides primitives for building, training, and running a decoder-only
transformer with RoPE, SwiGLU MLP, RMSNorm, and KV-cache attention.
"""

from __future__ import annotations

import json
import math
import os
import random
from collections.abc import Callable
from typing import Any, TypeGuard

from .autograd import Value


def _is_matrix_state_val(
    val: list[list[Value]] | list[Value],
) -> TypeGuard[list[list[Value]]]:
    """TypeGuard: check if a state_dict value is a weight matrix."""
    return bool(val) and isinstance(val[0], list)


def _is_vector_state_val(
    val: list[list[Value]] | list[Value],
) -> TypeGuard[list[Value]]:
    """TypeGuard: check if a state_dict value is a gain/bias vector."""
    return bool(val) and not isinstance(val[0], list)


def matrix(nout: int, nin: int, std: float = 0.08) -> list[list[Value]]:
    """Create an ``nout x nin`` matrix of Gaussian-initialized ``Value``s."""
    return [[Value(random.gauss(0.0, std)) for _ in range(nin)] for _ in range(nout)]


def linear(x: list[Value], w: list[list[Value]]) -> list[Value]:
    """Compute a matrix-vector product returning a list of ``Value``s."""
    return [
        sum((wi * xi for wi, xi in zip(wo, x, strict=True)), Value(0.0)) for wo in w
    ]


def softmax(logits: list[Value]) -> list[Value]:
    """Compute numerically-stable softmax over a list of ``Value`` logits."""
    max_val = max(val.data for val in logits)
    exps = [(val - max_val).exp() for val in logits]
    total = sum(exps)
    return [e / total for e in exps]


def rmsnorm(x: list[Value]) -> list[Value]:
    """Apply RMS normalization to a list of ``Value``s."""
    ms = sum(xi * xi for xi in x) / len(x)
    scale = (ms + 1e-5) ** -0.5
    return [xi * scale for xi in x]


def precompute_rope(
    seq_len: int, head_dim: int, theta: float = 10000.0
) -> tuple[list[list[float]], list[list[float]]]:
    """Precompute half-split RoPE cos/sin tables.
    Returns (cos_table, sin_table) each [seq_len][head_dim//2].
    Half-split convention: pairs dim i with dim i + head_dim/2.
    """
    half = head_dim // 2
    inv_freq = [1.0 / (theta ** (2.0 * i / head_dim)) for i in range(half)]
    cos_table: list[list[float]] = []
    sin_table: list[list[float]] = []
    for pos in range(seq_len):
        cos_table.append([math.cos(pos * f) for f in inv_freq])
        sin_table.append([math.sin(pos * f) for f in inv_freq])
    return cos_table, sin_table


def apply_rope(
    vector: list[Value],
    pos: int,
    cos_table: list[list[float]],
    sin_table: list[list[float]],
) -> list[Value]:
    """Apply half-split (rotate_half) RoPE rotation to a Value vector.
    Pairs dimension i with dimension i + len(vector)//2.
    """
    d = len(vector)
    half = d // 2
    cr, sr = cos_table[pos], sin_table[pos]
    result: list[Value] = [Value(0.0) for _ in range(d)]
    for i in range(half):
        x1 = vector[i]
        x2 = vector[i + half]
        c = cr[i]
        s = sr[i]
        result[i] = x1 * c - x2 * s
        result[i + half] = x2 * c + x1 * s
    return result


class LlamaModel:
    """A decoder-only transformer with RoPE, SwiGLU MLP, RMSNorm, and KV-cache."""

    def __init__(
        self,
        vocab_size: int,
        n_embd: int = 16,
        n_head: int = 4,
        n_layer: int = 1,
        block_size: int = 16,
    ) -> None:
        self.vocab_size = vocab_size
        self.n_embd = n_embd
        self.n_head = n_head
        self.n_layer = n_layer
        self.block_size = block_size
        self.head_dim = n_embd // n_head
        self.intermediate_size = int(8 * n_embd / 3)

        if self.head_dim % 2 != 0:
            raise ValueError(f"head_dim={self.head_dim} must be even for RoPE")

        self.state_dict: dict[str, list[list[Value]] | list[Value]] = {
            "wte": matrix(vocab_size, n_embd),
            "lm_head": matrix(vocab_size, n_embd),
        }
        for i in range(n_layer):
            self.state_dict[f"layer{i}.attn_wq"] = matrix(n_embd, n_embd)
            self.state_dict[f"layer{i}.attn_wk"] = matrix(n_embd, n_embd)
            self.state_dict[f"layer{i}.attn_wv"] = matrix(n_embd, n_embd)
            self.state_dict[f"layer{i}.attn_wo"] = matrix(n_embd, n_embd)
            self.state_dict[f"layer{i}.mlp_gate"] = matrix(
                self.intermediate_size, n_embd
            )
            self.state_dict[f"layer{i}.mlp_up"] = matrix(self.intermediate_size, n_embd)
            self.state_dict[f"layer{i}.mlp_down"] = matrix(
                n_embd, self.intermediate_size
            )
            self.state_dict[f"layer{i}.rms_1"] = [Value(1.0) for _ in range(n_embd)]
            self.state_dict[f"layer{i}.rms_2"] = [Value(1.0) for _ in range(n_embd)]
        self.state_dict["rms_final"] = [Value(1.0) for _ in range(n_embd)]

        self.chars = None  # type: list[str] | None
        self.tokenizer_family: str = "char"
        self.serialization_type: str = "char_json"
        self.params: list[Value] = []
        for mat in self.state_dict.values():
            if _is_matrix_state_val(mat):
                for row in mat:
                    self.params.extend(row)
            elif _is_vector_state_val(mat):
                self.params.extend(mat)

        self._cos_table, self._sin_table = precompute_rope(
            self.block_size, self.head_dim, theta=10000.0
        )

    def _get_matrix(self, key: str) -> list[list[Value]]:
        """Access a matrix from ``state_dict`` (weight matrix)."""
        v = self.state_dict[key]
        assert _is_matrix_state_val(v)
        return v

    def _get_vector(self, key: str) -> list[Value]:
        """Access a vector from ``state_dict`` (gain/bias vector)."""
        v = self.state_dict[key]
        assert _is_vector_state_val(v)
        return v

    def forward(
        self,
        token_id: int,
        pos_id: int,
        keys: list[list[list[Value]]],
        values: list[list[list[Value]]],
    ) -> list[Value]:
        """Run one forward pass for a single token at the given position.

        Parameters
        ----------
        token_id : int
            The token index to embed and process.
        pos_id : int
            The sequence position for RoPE computation.
        keys : list of list of list of Value
            KV-cache for keys, indexed by layer then position.
        values : list of list of list of Value
            KV-cache for values, indexed by layer then position.

        Returns
        -------
        list of Value
            Logits over the vocabulary for this token position.
        """
        tok_emb = self._get_matrix("wte")[token_id]
        x = tok_emb

        for li in range(self.n_layer):
            x_residual = x
            r = [
                r * xi
                for r, xi in zip(
                    self._get_vector(f"layer{li}.rms_1"),
                    rmsnorm(x),
                    strict=True,
                )
            ]
            q = linear(r, self._get_matrix(f"layer{li}.attn_wq"))
            k = linear(r, self._get_matrix(f"layer{li}.attn_wk"))
            v = linear(r, self._get_matrix(f"layer{li}.attn_wv"))
            # Apply RoPE per-head, then cache rotated keys
            q_rotated = []
            k_rotated = []
            for h in range(self.n_head):
                hs = h * self.head_dim
                q_slice = q[hs : hs + self.head_dim]
                k_slice = k[hs : hs + self.head_dim]
                q_rotated.extend(
                    apply_rope(q_slice, pos_id, self._cos_table, self._sin_table)
                )
                k_rotated.extend(
                    apply_rope(k_slice, pos_id, self._cos_table, self._sin_table)
                )
            q = q_rotated
            k = k_rotated
            keys[li].append(k)
            values[li].append(v)
            x_attn = []
            for h in range(self.n_head):
                hs = h * self.head_dim
                q_h = q[hs : hs + self.head_dim]
                k_h: list[list[Value]] = [
                    ki[hs : hs + self.head_dim] for ki in keys[li]
                ]
                v_h: list[list[Value]] = [
                    vi[hs : hs + self.head_dim] for vi in values[li]
                ]
                attn_logits = [
                    sum(
                        (q_h[j] * k_h[t][j] for j in range(self.head_dim)),
                        Value(0.0),
                    )
                    / self.head_dim**0.5
                    for t in range(len(k_h))
                ]
                attn_weights = softmax(attn_logits)
                head_out = [
                    sum(
                        (attn_weights[t] * v_h[t][j] for t in range(len(v_h))),
                        Value(0.0),
                    )
                    for j in range(self.head_dim)
                ]
                x_attn.extend(head_out)
            x = linear(x_attn, self._get_matrix(f"layer{li}.attn_wo"))
            x = [a + b for a, b in zip(x, x_residual, strict=True)]

            x_residual = x
            r2 = [
                r * xi
                for r, xi in zip(
                    self._get_vector(f"layer{li}.rms_2"),
                    rmsnorm(x),
                    strict=True,
                )
            ]
            gate = linear(r2, self._get_matrix(f"layer{li}.mlp_gate"))
            gate = [gi.silu() for gi in gate]
            up = linear(r2, self._get_matrix(f"layer{li}.mlp_up"))
            combined = [g * u for g, u in zip(gate, up, strict=True)]
            x = linear(combined, self._get_matrix(f"layer{li}.mlp_down"))
            x = [a + b for a, b in zip(x, x_residual, strict=True)]

        n = [
            r * xi
            for r, xi in zip(
                self._get_vector("rms_final"),
                rmsnorm(x),
                strict=True,
            )
        ]
        logits = linear(n, self._get_matrix("lm_head"))
        return logits

    def num_params(self) -> int:
        """Return the total number of trainable parameters."""
        return len(self.params)

    def save(self, path: str, chars: list[str] | None = None) -> None:
        """Serialize the model to a JSON file.

        Parameters
        ----------
        path : str
            Filesystem path for the output JSON file.
        chars : list of str or None, optional
            Optional character mapping to include in the saved data.
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        serialized: dict[str, list[list[float]] | list[float]] = {}
        for k in self.state_dict:
            mat = self.state_dict[k]
            if _is_matrix_state_val(mat):
                serialized[k] = [[p.data for p in row] for row in mat]
            elif _is_vector_state_val(mat):
                serialized[k] = [p.data for p in mat]

        data = {
            "vocab_size": self.vocab_size,
            "n_embd": self.n_embd,
            "n_head": self.n_head,
            "n_layer": self.n_layer,
            "block_size": self.block_size,
            "intermediate_size": self.intermediate_size,
            "tokenizer_family": "char",
            "serialization_type": "char_json",
            "chars": chars,
            "state_dict": serialized,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    @classmethod
    def load(cls, path: str) -> LlamaModel:
        """Load a serialized ``LlamaModel`` from a JSON file.

        Parameters
        ----------
        path : str
            Filesystem path to the saved JSON checkpoint.

        Returns
        -------
        LlamaModel
            The deserialized model instance.

        Raises
        ------
        ValueError
            If the file contains an old GPT-2 format checkpoint.
        """
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        if "wpe" in data["state_dict"]:
            raise ValueError(
                "Old GPT-2 format detected. "
                "This model was saved with the old GPT-2 architecture "
                "(includes wpe/learned position embeddings, ReLU MLP). "
                "It cannot be loaded into the new Llama architecture."
            )

        model = cls(
            vocab_size=data["vocab_size"],
            n_embd=data["n_embd"],
            n_head=data["n_head"],
            n_layer=data["n_layer"],
            block_size=data["block_size"],
        )

        for k in data["state_dict"]:
            mat_data = data["state_dict"][k]
            mat = model.state_dict[k]
            if _is_matrix_state_val(mat):
                for i, row in enumerate(mat_data):
                    for j, val in enumerate(row):
                        mat[i][j].data = val
            elif _is_vector_state_val(mat):
                for i, val in enumerate(mat_data):
                    mat[i].data = val

        model.chars = data.get("chars")
        model.tokenizer_family = data.get("tokenizer_family", "char")
        model.serialization_type = data.get("serialization_type", "char_json")
        return model

    def forward_introspect(self, token_ids: list[int]) -> dict[str, Any]:
        """Run forward pass over multiple tokens and return introspection data.

        Similar to ``forward`` but processes a full sequence and returns
        attention weights, per-token embeddings, and final logits for
        visualization in the web UI.

        Parameters
        ----------
        token_ids : list of int
            Sequence of token indices to process.

        Returns
        -------
        dict
            A dictionary with keys ``attention``, ``logits``,
            ``embeddings``, ``n_layer``, ``n_head``, and ``tokens``.
        """
        keys: list[list[list[Value]]] = [[] for _ in range(self.n_layer)]
        values: list[list[list[Value]]] = [[] for _ in range(self.n_layer)]
        all_embeddings: list[list[float]] = []
        final_logits = None
        n_pos = len(token_ids)

        attention_weights_mat: list[list[list[list[float]]]] = [
            [[[] for _ in range(n_pos)] for _ in range(self.n_head)]
            for _ in range(self.n_layer)
        ]

        for pos_id, token_id in enumerate(token_ids):
            tok_emb = self._get_matrix("wte")[token_id]
            x = tok_emb
            all_embeddings.append([v.data for v in x])

            for li in range(self.n_layer):
                x_residual = x
                r = [
                    r * xi
                    for r, xi in zip(
                        self._get_vector(f"layer{li}.rms_1"),
                        rmsnorm(x),
                        strict=True,
                    )
                ]
                q = linear(r, self._get_matrix(f"layer{li}.attn_wq"))
                k = linear(r, self._get_matrix(f"layer{li}.attn_wk"))
                v = linear(r, self._get_matrix(f"layer{li}.attn_wv"))
                q_rotated = []
                k_rotated = []
                for h in range(self.n_head):
                    hs = h * self.head_dim
                    q_slice = q[hs : hs + self.head_dim]
                    k_slice = k[hs : hs + self.head_dim]
                    q_rotated.extend(
                        apply_rope(q_slice, pos_id, self._cos_table, self._sin_table)
                    )
                    k_rotated.extend(
                        apply_rope(k_slice, pos_id, self._cos_table, self._sin_table)
                    )
                q = q_rotated
                k = k_rotated
                keys[li].append(k)
                values[li].append(v)
                x_attn = []
                for h in range(self.n_head):
                    hs = h * self.head_dim
                    q_h = q[hs : hs + self.head_dim]
                    k_h: list[list[Value]] = [
                        ki[hs : hs + self.head_dim] for ki in keys[li]
                    ]
                    v_h: list[list[Value]] = [
                        vi[hs : hs + self.head_dim] for vi in values[li]
                    ]
                    attn_logits = [
                        sum(
                            (q_h[j] * k_h[t][j] for j in range(self.head_dim)),
                            Value(0.0),
                        )
                        / self.head_dim**0.5
                        for t in range(len(k_h))
                    ]
                    attn_weights = softmax(attn_logits)
                    attention_weights_mat[li][h][pos_id] = [
                        w.data for w in attn_weights
                    ]
                    head_out = [
                        sum(
                            (attn_weights[t] * v_h[t][j] for t in range(len(v_h))),
                            Value(0.0),
                        )
                        for j in range(self.head_dim)
                    ]
                    x_attn.extend(head_out)
                x = linear(x_attn, self._get_matrix(f"layer{li}.attn_wo"))
                x = [a + b for a, b in zip(x, x_residual, strict=True)]

                x_residual = x
                r2 = [
                    r * xi
                    for r, xi in zip(
                        self._get_vector(f"layer{li}.rms_2"),
                        rmsnorm(x),
                        strict=True,
                    )
                ]
                gate = linear(r2, self._get_matrix(f"layer{li}.mlp_gate"))
                gate = [gi.silu() for gi in gate]
                up = linear(r2, self._get_matrix(f"layer{li}.mlp_up"))
                combined = [g * u for g, u in zip(gate, up, strict=True)]
                x = linear(combined, self._get_matrix(f"layer{li}.mlp_down"))
                x = [a + b for a, b in zip(x, x_residual, strict=True)]

            n = [
                r * xi
                for r, xi in zip(
                    self._get_vector("rms_final"),
                    rmsnorm(x),
                    strict=True,
                )
            ]
            final_logits = linear(n, self._get_matrix("lm_head"))

        return {
            "attention": attention_weights_mat,
            "logits": final_logits,
            "embeddings": all_embeddings,
            "n_layer": self.n_layer,
            "n_head": self.n_head,
            "tokens": token_ids,
        }


def train(
    docs: list[str],
    model: LlamaModel | None = None,
    num_steps: int = 1000,
    block_size: int = 16,
    n_embd: int = 16,
    n_head: int = 4,
    n_layer: int = 1,
    learning_rate: float = 0.01,
    beta1: float = 0.85,
    beta2: float = 0.99,
    temperature: float = 0.5,
    progress_callback: Callable[..., Any] | None = None,
    optimizer_state_callback: (
        Callable[[int, list[float], list[float], list[float]], Any] | None
    ) = None,
    stop_check: Callable[[], bool] | None = None,
) -> tuple[LlamaModel, float, list[str], list[str]]:
    """Train a ``LlamaModel`` on character-level text data.

    Implements the full training loop: tokenization, cross-entropy loss,
    backward pass, hand-rolled Adam optimizer with linear LR decay, and
    final sampling of generated text.

    Parameters
    ----------
    docs : list of str
        List of document strings to train on.
    model : LlamaModel or None, optional
        Existing model to continue training, or None to create a new one.
    num_steps : int, optional
        Number of training steps. Defaults to 1000.
    block_size : int, optional
        Context length per step. Defaults to 16.
    n_embd : int, optional
        Embedding dimension for new models. Defaults to 16.
    n_head : int, optional
        Number of attention heads for new models. Defaults to 4.
    n_layer : int, optional
        Number of layers for new models. Defaults to 1.
    learning_rate : float, optional
        Initial learning rate. Defaults to 0.01.
    beta1 : float, optional
        Adam beta1. Defaults to 0.85.
    beta2 : float, optional
        Adam beta2. Defaults to 0.99.
    temperature : float, optional
        Sampling temperature. Defaults to 0.5.
    progress_callback : callable or None, optional
        Called each step with ``(step, loss, *, tokens, grad_norm)``.
    optimizer_state_callback : callable or None, optional
        Called each step with ``(step, m, v, grads)``.
    stop_check : callable or None, optional
        Called each step; if returns True, training halts early.

    Returns
    -------
    tuple
        ``(model, loss, samples, uchars)`` where ``model`` is the trained
        ``LlamaModel``, ``loss`` is the final loss, ``samples`` is a list
        of generated strings, and ``uchars`` is the sorted unique chars.
    """
    random.seed(42)

    if model is None:
        uchars = sorted(set("".join(docs)))
        BOS = len(uchars)
        vocab_size = len(uchars) + 1
        model = LlamaModel(vocab_size, n_embd, n_head, n_layer, block_size)
        m = [0.0] * len(model.params)
        v = [0.0] * len(model.params)
    else:
        if model.chars is not None:
            # Warm-start: inherit vocabulary from base model
            uchars = list(model.chars)
            BOS = len(uchars)
            vocab_size = model.vocab_size
            block_size = model.block_size
            # Check for OOV characters in the new docs
            vocab_set = set(model.chars)
            unsupported: set[str] = set()
            for doc in docs:
                for ch in doc:
                    if ch not in vocab_set:
                        unsupported.add(ch)
            if unsupported:
                sample = sorted(unsupported)[:5]
                raise ValueError(
                    f"Document contains {len(unsupported)} character(s) "
                    f"not in base vocabulary: {sample}"
                )
        else:
            # Backward compat: compute from docs, verify against model
            uchars = sorted(set("".join(docs)))
            BOS = len(uchars)
            vocab_size = model.vocab_size
            block_size = model.block_size
            if model.vocab_size != len(uchars) + 1:
                raise ValueError(
                    f"Model vocab_size={model.vocab_size} does not match "
                    f"computed vocab_size={len(uchars) + 1} from docs. "
                    "Save and reload the model with chars metadata."
                )
        m = [0.0] * len(model.params)
        v = [0.0] * len(model.params)

    random.shuffle(docs)

    loss: Value = Value(0.0)

    for step in range(num_steps):
        if stop_check is not None and stop_check():
            break
        doc = docs[step % len(docs)]
        tokens = [BOS] + [uchars.index(ch) for ch in doc] + [BOS]
        n = min(block_size, len(tokens) - 1)
        keys: list[list[list[Value]]] = [[] for _ in range(model.n_layer)]
        values: list[list[list[Value]]] = [[] for _ in range(model.n_layer)]
        losses = []
        for pos_id in range(n):
            token_id, target_id = tokens[pos_id], tokens[pos_id + 1]
            logits = model.forward(token_id, pos_id, keys, values)
            probs = softmax(logits)
            loss_t = -probs[target_id].log()
            losses.append(loss_t)
        loss = (1.0 / n) * sum(losses, Value(0.0))
        loss.backward()
        lr_t = learning_rate * (1 - step / num_steps)
        for i, p in enumerate(model.params):
            m[i] = beta1 * m[i] + (1 - beta1) * p.grad
            v[i] = beta2 * v[i] + (1 - beta2) * p.grad**2
            m_hat = m[i] / (1 - beta1 ** (step + 1))
            v_hat = v[i] / (1 - beta2 ** (step + 1))
            p.data -= lr_t * m_hat / (v_hat**0.5 + 1e-8)
        if optimizer_state_callback:
            grads = [p.grad for p in model.params]
            optimizer_state_callback(step, m, v, grads)
        for p in model.params:
            p.grad = 0
        if progress_callback:
            progress_callback(step, loss.data, tokens=n, grad_norm=None)

    samples = []
    for _ in range(20):
        sample_keys: list[list[list[Value]]] = [[] for _ in range(model.n_layer)]
        sample_vals: list[list[list[Value]]] = [[] for _ in range(model.n_layer)]
        token_id = BOS
        sample = []
        for pos_id in range(block_size):
            logits = model.forward(token_id, pos_id, sample_keys, sample_vals)
            scaled = [logit / temperature for logit in logits]
            probs = softmax(scaled)
            token_id = random.choices(
                range(vocab_size), weights=[p.data for p in probs]
            )[0]
            if token_id == BOS:
                break
            sample.append(uchars[token_id])
        samples.append("".join(sample))

    return model, loss.data, samples, uchars
