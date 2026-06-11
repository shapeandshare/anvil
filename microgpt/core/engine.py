import random

from microgpt.core.autograd import Value


def matrix(nout, nin, std=0.08):
    return [[Value(random.gauss(0, std)) for _ in range(nin)] for _ in range(nout)]


def linear(x, w):
    return [sum(wi * xi for wi, xi in zip(wo, x, strict=False)) for wo in w]


def softmax(logits):
    max_val = max(val.data for val in logits)
    exps = [(val - max_val).exp() for val in logits]
    total = sum(exps)
    return [e / total for e in exps]


def rmsnorm(x):
    ms = sum(xi * xi for xi in x) / len(x)
    scale = (ms + 1e-5) ** -0.5
    return [xi * scale for xi in x]


class GPT:
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
        self.state_dict = {
            "wte": matrix(vocab_size, n_embd),
            "wpe": matrix(block_size, n_embd),
            "lm_head": matrix(vocab_size, n_embd),
        }
        for i in range(n_layer):
            self.state_dict[f"layer{i}.attn_wq"] = matrix(n_embd, n_embd)
            self.state_dict[f"layer{i}.attn_wk"] = matrix(n_embd, n_embd)
            self.state_dict[f"layer{i}.attn_wv"] = matrix(n_embd, n_embd)
            self.state_dict[f"layer{i}.attn_wo"] = matrix(n_embd, n_embd)
            self.state_dict[f"layer{i}.mlp_fc1"] = matrix(4 * n_embd, n_embd)
            self.state_dict[f"layer{i}.mlp_fc2"] = matrix(n_embd, 4 * n_embd)
        self.params = [
            p for mat in self.state_dict.values() for row in mat for p in row
        ]

    def forward(self, token_id, pos_id, keys, values):
        tok_emb = self.state_dict["wte"][token_id]
        pos_emb = self.state_dict["wpe"][pos_id]
        x = [t + p for t, p in zip(tok_emb, pos_emb, strict=False)]
        x = rmsnorm(x)
        for li in range(self.n_layer):
            x_residual = x
            x = rmsnorm(x)
            q = linear(x, self.state_dict[f"layer{li}.attn_wq"])
            k = linear(x, self.state_dict[f"layer{li}.attn_wk"])
            v = linear(x, self.state_dict[f"layer{li}.attn_wv"])
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
            x = [a + b for a, b in zip(x, x_residual, strict=False)]
            x_residual = x
            x = rmsnorm(x)
            x = linear(x, self.state_dict[f"layer{li}.mlp_fc1"])
            x = [xi.relu() for xi in x]
            x = linear(x, self.state_dict[f"layer{li}.mlp_fc2"])
            x = [a + b for a, b in zip(x, x_residual, strict=False)]
        logits = linear(x, self.state_dict["lm_head"])
        return logits

    def num_params(self):
        return len(self.params)

    def save(self, path: str, chars: list[str] | None = None) -> None:
        import json
        import os

        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "vocab_size": self.vocab_size,
            "n_embd": self.n_embd,
            "n_head": self.n_head,
            "n_layer": self.n_layer,
            "block_size": self.block_size,
            "chars": chars,
            "state_dict": {
                k: [[p.data for p in row] for row in mat]
                for k, mat in self.state_dict.items()
            },
        }
        with open(path, "w") as f:
            json.dump(data, f)

    


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
):
    random.seed(42)
    uchars = sorted(set("".join(docs)))
    BOS = len(uchars)
    vocab_size = len(uchars) + 1

    if model is None:
        model = GPT(vocab_size, n_embd, n_head, n_layer, block_size)
        m = [0.0] * len(model.params)
        v = [0.0] * len(model.params)
    else:
        m = [0.0] * len(model.params)
        v = [0.0] * len(model.params)

    random.shuffle(docs)

    for step in range(num_steps):
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
            p.grad = 0
        if progress_callback:
            progress_callback(step, loss.data)

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
