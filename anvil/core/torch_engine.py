"""Torch-based GPU-accelerated training engine for anvil.

This module mirrors ``anvil.core.engine`` but uses PyTorch tensors
and autograd so training can run on CUDA or MPS devices.

It is an optional backend — torch must be installed (``pip install torch``).
"""

from __future__ import annotations

import random
from typing import Any

_TORCH_AVAILABLE: bool = False
try:
    import torch
    import torch.nn.functional as F

    _TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]


def torch_available() -> bool:
    return _TORCH_AVAILABLE


class TorchGPT:
    """GPT architecture built with torch.nn parameters.

    Mirrors the architecture of ``anvil.core.engine.GPT`` but uses
    torch tensors and autograd for GPU-accelerated training.
    Only usable when torch is installed (check ``torch_available()``).
    """

    def __init__(
        self,
        vocab_size: int,
        n_embd: int = 16,
        n_head: int = 4,
        n_layer: int = 1,
        block_size: int = 16,
    ):
        if not _TORCH_AVAILABLE:
            raise RuntimeError("torch is not installed")
        self.vocab_size = vocab_size
        self.n_embd = n_embd
        self.n_head = n_head
        self.n_layer = n_layer
        self.block_size = block_size
        self.head_dim = n_embd // n_head

        self.wte = torch.nn.Parameter(torch.randn(vocab_size, n_embd) * 0.08)
        self.wpe = torch.nn.Parameter(torch.randn(block_size, n_embd) * 0.08)
        self.lm_head = torch.nn.Parameter(torch.randn(vocab_size, n_embd) * 0.08)

        self.attn_wq = torch.nn.ParameterList()
        self.attn_wk = torch.nn.ParameterList()
        self.attn_wv = torch.nn.ParameterList()
        self.attn_wo = torch.nn.ParameterList()
        self.mlp_fc1 = torch.nn.ParameterList()
        self.mlp_fc2 = torch.nn.ParameterList()

        for _ in range(n_layer):
            self.attn_wq.append(
                torch.nn.Parameter(torch.randn(n_embd, n_embd) * 0.08)
            )
            self.attn_wk.append(
                torch.nn.Parameter(torch.randn(n_embd, n_embd) * 0.08)
            )
            self.attn_wv.append(
                torch.nn.Parameter(torch.randn(n_embd, n_embd) * 0.08)
            )
            self.attn_wo.append(
                torch.nn.Parameter(torch.randn(n_embd, n_embd) * 0.08)
            )
            self.mlp_fc1.append(
                torch.nn.Parameter(torch.randn(4 * n_embd, n_embd) * 0.08)
            )
            self.mlp_fc2.append(
                torch.nn.Parameter(torch.randn(n_embd, 4 * n_embd) * 0.08)
            )

    @property
    def num_params(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def parameters(self):
        if not _TORCH_AVAILABLE:
            return []
        for v in vars(self).values():
            if isinstance(v, torch.nn.Parameter):
                yield v
            elif isinstance(v, torch.nn.ParameterList):
                yield from v

    def forward(self, token_id: int, pos_id: int, keys: list[list], values: list[list]):
        tok_emb = self.wte[token_id]
        pos_emb = self.wpe[pos_id]
        x = tok_emb + pos_emb
        x = F.rms_norm(x, normalized_shape=(self.n_embd,), eps=1e-5)

        for li in range(self.n_layer):
            x_residual = x
            x = F.rms_norm(x, normalized_shape=(self.n_embd,), eps=1e-5)

            q = F.linear(x, self.attn_wq[li])
            k = F.linear(x, self.attn_wk[li])
            v = F.linear(x, self.attn_wv[li])

            keys[li].append(k)
            values[li].append(v)

            x_attn_parts = []
            for h in range(self.n_head):
                hs = h * self.head_dim
                q_h = q[hs : hs + self.head_dim]

                # Stack all previous keys/values for this head
                k_h = torch.stack(
                    [ki[hs : hs + self.head_dim] for ki in keys[li]]
                )  # (T, head_dim)
                v_h = torch.stack(
                    [vi[hs : hs + self.head_dim] for vi in values[li]]
                )  # (T, head_dim)

                # attn_logits[t] = q_h · k_h[t] / sqrt(head_dim)
                attn_logits = torch.mv(k_h, q_h) / (self.head_dim**0.5)  # (T,)
                attn_weights = F.softmax(attn_logits, dim=0)  # (T,)

                # head_out = weighted sum of values
                head_out = v_h.T @ attn_weights  # (head_dim,)
                x_attn_parts.append(head_out)

            x_attn = torch.cat(x_attn_parts)
            x = F.linear(x_attn, self.attn_wo[li])
            x = x + x_residual

            x_residual = x
            x = F.rms_norm(x, normalized_shape=(self.n_embd,), eps=1e-5)
            x = F.linear(x, self.mlp_fc1[li])
            x = F.relu(x)
            x = F.linear(x, self.mlp_fc2[li])
            x = x + x_residual

        logits = F.linear(x, self.lm_head)
        return logits

    def to(self, device):
        for v in vars(self).values():
            if isinstance(v, torch.nn.Parameter):
                v.data = v.data.to(device)
            elif isinstance(v, torch.nn.ParameterList):
                for p in v:
                    p.data = p.data.to(device)
        return self

    def eval(self):
        pass

    def export_weights(self) -> dict[str, list[list[float]]]:
        sd: dict[str, list[list[float]]] = {}
        sd["wte"] = self.wte.detach().cpu().tolist()
        sd["wpe"] = self.wpe.detach().cpu().tolist()
        sd["lm_head"] = self.lm_head.detach().cpu().tolist()

        for li in range(self.n_layer):
            sd[f"layer{li}.attn_wq"] = self.attn_wq[li].detach().cpu().tolist()
            sd[f"layer{li}.attn_wk"] = self.attn_wk[li].detach().cpu().tolist()
            sd[f"layer{li}.attn_wv"] = self.attn_wv[li].detach().cpu().tolist()
            sd[f"layer{li}.attn_wo"] = self.attn_wo[li].detach().cpu().tolist()
            sd[f"layer{li}.mlp_fc1"] = self.mlp_fc1[li].detach().cpu().tolist()
            sd[f"layer{li}.mlp_fc2"] = self.mlp_fc2[li].detach().cpu().tolist()

        return sd


def train_torch(
    docs: list[str],
    device: str = "cpu",
    num_steps: int = 1000,
    block_size: int = 16,
    n_embd: int = 16,
    n_head: int = 4,
    n_layer: int = 1,
    learning_rate: float = 0.01,
    beta1: float = 0.85,
    beta2: float = 0.99,
    temperature: float = 0.5,
    progress_callback: Any = None,
    stop_check: Any = None,
) -> tuple[dict[str, list[list[float]]], float, list[str], list[str]]:
    if not _TORCH_AVAILABLE:
        msg = "torch is not installed — cannot run GPU training"
        raise RuntimeError(msg)

    torch.manual_seed(42)
    device_obj = torch.device(device)

    uchars = sorted(set("".join(docs)))
    BOS = len(uchars)
    vocab_size = len(uchars) + 1

    model = TorchGPT(vocab_size, n_embd, n_head, n_layer, block_size)
    model.to(device_obj)

    optim = torch.optim.Adam(
        model.parameters(), lr=learning_rate, betas=(beta1, beta2), eps=1e-8
    )
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optim, lr_lambda=lambda step: 1 - step / num_steps
    )

    random.shuffle(docs)
    final_loss_val: float = 0.0

    for step in range(num_steps):
        if stop_check is not None and stop_check():
            break
        doc = docs[step % len(docs)]
        tokens = [BOS] + [uchars.index(ch) for ch in doc] + [BOS]
        n = min(block_size, len(tokens) - 1)

        keys = [[] for _ in range(n_layer)]
        values = [[] for _ in range(n_layer)]

        total_loss = torch.tensor(0.0, device=device_obj)

        for pos_id in range(n):
            token_id = tokens[pos_id]
            target_id = tokens[pos_id + 1]

            logits = model.forward(token_id, pos_id, keys, values)
            probs = F.softmax(logits, dim=0)
            loss_t = -torch.log(probs[target_id] + 1e-10)
            total_loss = total_loss + loss_t

        loss = total_loss / n

        optim.zero_grad()
        loss.backward()
        optim.step()
        scheduler.step()

        loss_val = loss.item()
        final_loss_val = loss_val

        if progress_callback is not None:
            progress_callback(step, loss_val)

    samples: list[str] = []
    with torch.no_grad():
        for _ in range(20):
            token_id = BOS
            sample: list[str] = []
            samp_keys = [[] for _ in range(model.n_layer)]
            samp_values = [[] for _ in range(model.n_layer)]
            for pos_id in range(block_size):
                logits = model.forward(token_id, pos_id, samp_keys, samp_values)
                scaled = logits / temperature
                probs = F.softmax(scaled, dim=0)
                probs_np = probs.cpu().numpy()
                chosen = random.choices(range(vocab_size), weights=probs_np)[0]
                if chosen == BOS:
                    break
                sample.append(uchars[chosen])
                token_id = chosen
            samples.append("".join(sample))

    exported = model.export_weights()
    return exported, final_loss_val, samples, uchars