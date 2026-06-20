import math
import random

from anvil.core.autograd import Value


def matrix(nout, nin, std=0.08):
    return [[Value(random.gauss(0, std)) for _ in range(nin)] for _ in range(nout)]


def linear(x, w):
    return [sum(wi * xi for wi, xi in zip(wo, x, strict=True)) for wo in w]


def softmax(logits):
    max_val = max(val.data for val in logits)
    exps = [(val - max_val).exp() for val in logits]
    total = sum(exps)
    return [e / total for e in exps]


def rmsnorm(x):
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
    vector: list[float],
    pos: int,
    cos_table: list[list[float]],
    sin_table: list[list[float]],
) -> list[float]:
    """Apply half-split (rotate_half) RoPE rotation to a vector.
    Pairs dimension i with dimension i + len(vector)//2.
    """
    d = len(vector)
    half = d // 2
    cr, sr = cos_table[pos], sin_table[pos]
    result = [0.0] * d
    for i in range(half):
        x1 = vector[i]
        x2 = vector[i + half]
        c = cr[i]
        s = sr[i]
        result[i] = x1 * c - x2 * s
        result[i + half] = x2 * c + x1 * s
    return result


class LlamaModel:
    def __init__(
        self,
        vocab_size: int,
        n_embd: int = 16,
        n_head: int = 4,
        n_layer: int = 1,
        block_size: int = 16,
    ):
        self.vocab_size = vocab_size
        self.n_embd = n_embd
        self.n_head = n_head
        self.n_layer = n_layer
        self.block_size = block_size
        self.head_dim = n_embd // n_head
        self.intermediate_size = int(8 * n_embd / 3)

        if self.head_dim % 2 != 0:
            raise ValueError(f"head_dim={self.head_dim} must be even for RoPE")

        self.state_dict: dict[str, list] = {
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
        self.params: list[Value] = []
        for mat in self.state_dict.values():
            if isinstance(mat[0], list):
                for row in mat:
                    self.params.extend(row)
            else:
                self.params.extend(mat)

        self._cos_table, self._sin_table = precompute_rope(
            self.block_size, self.head_dim, theta=10000.0
        )

    def forward(self, token_id, pos_id, keys, values):
        tok_emb = self.state_dict["wte"][token_id]
        x = tok_emb

        for li in range(self.n_layer):
            x_residual = x
            r = [
                r * xi
                for r, xi in zip(
                    self.state_dict[f"layer{li}.rms_1"],
                    rmsnorm(x),
                    strict=True,
                )
            ]
            q = linear(r, self.state_dict[f"layer{li}.attn_wq"])
            k = linear(r, self.state_dict[f"layer{li}.attn_wk"])
            v = linear(r, self.state_dict[f"layer{li}.attn_wv"])
            # Apply RoPE per-head, then cache rotated keys
            q_rotated = []
            k_rotated = []
            for h in range(self.n_head):
                hs = h * self.head_dim
                q_h = q[hs : hs + self.head_dim]
                k_h = k[hs : hs + self.head_dim]
                q_rotated.extend(
                    apply_rope(q_h, pos_id, self._cos_table, self._sin_table)
                )
                k_rotated.extend(
                    apply_rope(k_h, pos_id, self._cos_table, self._sin_table)
                )
            q = q_rotated
            k = k_rotated
            keys[li].append(k)
            values[li].append(v)
            x_attn = []
            for h in range(self.n_head):
                hs = h * self.head_dim
                q_h = q[hs : hs + self.head_dim]
                k_h = [ki[hs : hs + self.head_dim] for ki in keys[li]]
                v_h = [vi[hs : hs + self.head_dim] for vi in values[li]]
                attn_logits = [
                    sum(q_h[j] * k_h[t][j] for j in range(self.head_dim))
                    / self.head_dim**0.5
                    for t in range(len(k_h))
                ]
                attn_weights = softmax(attn_logits)
                head_out = [
                    sum(attn_weights[t] * v_h[t][j] for t in range(len(v_h)))
                    for j in range(self.head_dim)
                ]
                x_attn.extend(head_out)
            x = linear(x_attn, self.state_dict[f"layer{li}.attn_wo"])
            x = [a + b for a, b in zip(x, x_residual, strict=True)]

            x_residual = x
            r2 = [
                r * xi
                for r, xi in zip(
                    self.state_dict[f"layer{li}.rms_2"],
                    rmsnorm(x),
                    strict=True,
                )
            ]
            gate = linear(r2, self.state_dict[f"layer{li}.mlp_gate"])
            gate = [gi.silu() for gi in gate]
            up = linear(r2, self.state_dict[f"layer{li}.mlp_up"])
            combined = [g * u for g, u in zip(gate, up, strict=True)]
            x = linear(combined, self.state_dict[f"layer{li}.mlp_down"])
            x = [a + b for a, b in zip(x, x_residual, strict=True)]

        n = [
            r * xi
            for r, xi in zip(
                self.state_dict["rms_final"],
                rmsnorm(x),
                strict=True,
            )
        ]
        logits = linear(n, self.state_dict["lm_head"])
        return logits

    def num_params(self):
        return len(self.params)

    def save(self, path: str, chars=None) -> None:
        import json
        import os

        os.makedirs(os.path.dirname(path), exist_ok=True)
        serialized: dict[str, list] = {}
        for k, mat in self.state_dict.items():
            if isinstance(mat[0], list):
                serialized[k] = [[p.data for p in row] for row in mat]
            else:
                serialized[k] = [p.data for p in mat]

        data = {
            "vocab_size": self.vocab_size,
            "n_embd": self.n_embd,
            "n_head": self.n_head,
            "n_layer": self.n_layer,
            "block_size": self.block_size,
            "intermediate_size": self.intermediate_size,
            "chars": chars,
            "state_dict": serialized,
        }
        with open(path, "w") as f:
            json.dump(data, f)

    @classmethod
    def load(cls, path: str) -> "LlamaModel":
        import json

        with open(path) as f:
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

        for k, mat_data in data["state_dict"].items():
            if isinstance(mat_data[0], list):
                for i, row in enumerate(mat_data):
                    for j, val in enumerate(row):
                        model.state_dict[k][i][j].data = val
            else:
                for i, val in enumerate(mat_data):
                    model.state_dict[k][i].data = val

        model.chars = data.get("chars")
        return model

    def forward_introspect(self, token_ids: list[int]) -> dict:
        keys = [[] for _ in range(self.n_layer)]
        values = [[] for _ in range(self.n_layer)]
        all_embeddings: list[list[float]] = []
        final_logits = None
        n_pos = len(token_ids)

        attention_weights_mat: list[list[list[list[float]]]] = [
            [[[] for _ in range(n_pos)] for _ in range(self.n_head)]
            for _ in range(self.n_layer)
        ]

        for pos_id, token_id in enumerate(token_ids):
            tok_emb = self.state_dict["wte"][token_id]
            x = tok_emb
            all_embeddings.append([v.data for v in x])

            for li in range(self.n_layer):
                x_residual = x
                r = [
                    r * xi
                    for r, xi in zip(
                        self.state_dict[f"layer{li}.rms_1"],
                        rmsnorm(x),
                        strict=True,
                    )
                ]
                q = linear(r, self.state_dict[f"layer{li}.attn_wq"])
                k = linear(r, self.state_dict[f"layer{li}.attn_wk"])
                v = linear(r, self.state_dict[f"layer{li}.attn_wv"])
                q_rotated = []
                k_rotated = []
                for h in range(self.n_head):
                    hs = h * self.head_dim
                    q_h = q[hs : hs + self.head_dim]
                    k_h = k[hs : hs + self.head_dim]
                    q_rotated.extend(
                        apply_rope(q_h, pos_id, self._cos_table, self._sin_table)
                    )
                    k_rotated.extend(
                        apply_rope(k_h, pos_id, self._cos_table, self._sin_table)
                    )
                q = q_rotated
                k = k_rotated
                keys[li].append(k)
                values[li].append(v)
                x_attn = []
                for h in range(self.n_head):
                    hs = h * self.head_dim
                    q_h = q[hs : hs + self.head_dim]
                    k_h = [ki[hs : hs + self.head_dim] for ki in keys[li]]
                    v_h = [vi[hs : hs + self.head_dim] for vi in values[li]]
                    attn_logits = [
                        sum(q_h[j] * k_h[t][j] for j in range(self.head_dim))
                        / self.head_dim**0.5
                        for t in range(len(k_h))
                    ]
                    attn_weights = softmax(attn_logits)
                    attention_weights_mat[li][h][pos_id] = [
                        w.data for w in attn_weights
                    ]
                    head_out = [
                        sum(attn_weights[t] * v_h[t][j] for t in range(len(v_h)))
                        for j in range(self.head_dim)
                    ]
                    x_attn.extend(head_out)
                x = linear(x_attn, self.state_dict[f"layer{li}.attn_wo"])
                x = [a + b for a, b in zip(x, x_residual, strict=True)]

                x_residual = x
                r2 = [
                    r * xi
                    for r, xi in zip(
                        self.state_dict[f"layer{li}.rms_2"],
                        rmsnorm(x),
                        strict=True,
                    )
                ]
                gate = linear(r2, self.state_dict[f"layer{li}.mlp_gate"])
                gate = [gi.silu() for gi in gate]
                up = linear(r2, self.state_dict[f"layer{li}.mlp_up"])
                combined = [g * u for g, u in zip(gate, up, strict=True)]
                x = linear(combined, self.state_dict[f"layer{li}.mlp_down"])
                x = [a + b for a, b in zip(x, x_residual, strict=True)]

            n = [
                r * xi
                for r, xi in zip(
                    self.state_dict["rms_final"],
                    rmsnorm(x),
                    strict=True,
                )
            ]
            final_logits = linear(n, self.state_dict["lm_head"])

        return {
            "attention": attention_weights_mat,
            "logits": final_logits,
            "embeddings": all_embeddings,
            "n_layer": self.n_layer,
            "n_head": self.n_head,
            "tokens": token_ids,
        }


def train(
    docs,
    model=None,
    num_steps=1000,
    block_size=16,
    n_embd=16,
    n_head=4,
    n_layer=1,
    learning_rate=0.01,
    beta1=0.85,
    beta2=0.99,
    temperature=0.5,
    progress_callback=None,
    optimizer_state_callback=None,
    stop_check=None,
):
    random.seed(42)
    uchars = sorted(set("".join(docs)))
    BOS = len(uchars)
    vocab_size = len(uchars) + 1

    if model is None:
        model = LlamaModel(vocab_size, n_embd, n_head, n_layer, block_size)
        m = [0.0] * len(model.params)
        v = [0.0] * len(model.params)
    else:
        m = [0.0] * len(model.params)
        v = [0.0] * len(model.params)

    random.shuffle(docs)

    for step in range(num_steps):
        if stop_check is not None and stop_check():
            break
        doc = docs[step % len(docs)]
        tokens = [BOS] + [uchars.index(ch) for ch in doc] + [BOS]
        n = min(block_size, len(tokens) - 1)
        keys = [[] for _ in range(model.n_layer)]
        values = [[] for _ in range(model.n_layer)]
        losses = []
        for pos_id in range(n):
            token_id, target_id = tokens[pos_id], tokens[pos_id + 1]
            logits = model.forward(token_id, pos_id, keys, values)
            probs = softmax(logits)
            loss_t = -probs[target_id].log()
            losses.append(loss_t)
        loss = (1.0 / n) * sum(losses)
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
        keys = [[] for _ in range(model.n_layer)]
        values = [[] for _ in range(model.n_layer)]
        token_id = BOS
        sample = []
        for pos_id in range(block_size):
            logits = model.forward(token_id, pos_id, keys, values)
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
