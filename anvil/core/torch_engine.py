# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Torch-based GPU-accelerated training engine for anvil.

This module mirrors ``anvil.core.engine`` but uses PyTorch tensors
and autograd so training can run on CUDA or MPS devices.

It is an optional backend — torch must be installed (``pip install torch``).
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Iterator
from types import ModuleType
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from torch import device as torch_device
    from torch.nn import Parameter as torch_Parameter

_TORCH_AVAILABLE: bool = False  # Whether torch was successfully imported
_torch_mod: ModuleType | None = None  # Imported torch module (or None)
_F_mod: ModuleType | None = None  # Imported torch.nn.functional module (or None)

try:
    import torch as _torch_import
    import torch.nn.functional as _F_import

    # Import torch.Tensor at runtime — used in cast() calls (not annotation-only).
    from torch import Tensor as torch_Tensor

    _torch_mod = _torch_import
    _F_mod = _F_import
    _TORCH_AVAILABLE = True
except ImportError:
    pass

# Public aliases — guarded by assert torch is not None / assert F is not None
torch: ModuleType | None = (
    _torch_mod  # Public torch module reference (check torch_available() first)
)
F: ModuleType | None = (
    _F_mod  # Public torch.nn.functional reference (check torch_available() first)
)


def torch_available() -> bool:
    """Check whether PyTorch is installed and importable.

    Returns
    -------
    bool
        ``True`` if ``torch`` was successfully imported, ``False``
        otherwise.
    """
    return _TORCH_AVAILABLE


class TorchLlamaModel:
    """Llama architecture built with torch.nn parameters.

    Mirrors the architecture of ``anvil.core.engine.LlamaModel`` but
    uses PyTorch tensors and autograd for GPU-accelerated training.
    Supports CPU, CUDA, and MPS devices.

    Only usable when torch is installed (check ``torch_available()``).

    Architecture components:
    - RoPE with precomputed cos/sin tables (half-split convention)
    - SwiGLU activation in MLP layers
    - RMSNorm with learned scale parameters via ``nn.Parameter``
    - Causal multi-head attention with key/value caching
    """

    def __init__(
        self,
        vocab_size: int,
        n_embd: int = 16,
        n_head: int = 4,
        n_layer: int = 1,
        block_size: int = 16,
    ):
        """Initialize the TorchLlamaModel with the given architecture.

        Constructs all parameter tensors (token embeddings, attention
        projections, SwiGLU MLP weights, RMSNorm scales) and
        precomputes the RoPE cos/sin tables for the given block size.

        Parameters
        ----------
        vocab_size : int
            Size of the vocabulary.
        n_embd : int, optional
            Embedding dimension. Defaults to ``16``.
        n_head : int, optional
            Number of attention heads. Defaults to ``4``.
        n_layer : int, optional
            Number of transformer layers. Defaults to ``1``.
        block_size : int, optional
            Maximum sequence length. Defaults to ``16``.

        Raises
        ------
        RuntimeError
            If PyTorch is not installed.
        ValueError
            If ``head_dim = n_embd // n_head`` is odd.
        """
        if not _TORCH_AVAILABLE:
            raise RuntimeError("torch is not installed")
        assert torch is not None
        assert F is not None
        self.vocab_size = vocab_size
        self.n_embd = n_embd
        self.n_head = n_head
        self.n_layer = n_layer
        self.block_size = block_size
        self.head_dim = n_embd // n_head

        if self.head_dim % 2 != 0:
            raise ValueError(f"head_dim={self.head_dim} must be even for RoPE")

        self.intermediate_size = int(8 * n_embd / 3)

        self.wte = torch.nn.Parameter(torch.randn(vocab_size, n_embd) * 0.08)
        self.lm_head = torch.nn.Parameter(torch.randn(vocab_size, n_embd) * 0.08)

        # RMSNorm learned scale parameters
        self.rms_final = torch.nn.Parameter(torch.ones(n_embd))
        self.rms_1 = torch.nn.ParameterList(
            [torch.nn.Parameter(torch.ones(n_embd)) for _ in range(n_layer)]
        )
        self.rms_2 = torch.nn.ParameterList(
            [torch.nn.Parameter(torch.ones(n_embd)) for _ in range(n_layer)]
        )

        # Attention parameters
        self.attn_wq = torch.nn.ParameterList()
        self.attn_wk = torch.nn.ParameterList()
        self.attn_wv = torch.nn.ParameterList()
        self.attn_wo = torch.nn.ParameterList()

        # SwiGLU MLP parameters
        self.mlp_gate = torch.nn.ParameterList()
        self.mlp_up = torch.nn.ParameterList()
        self.mlp_down = torch.nn.ParameterList()

        for _ in range(n_layer):
            self.attn_wq.append(torch.nn.Parameter(torch.randn(n_embd, n_embd) * 0.08))
            self.attn_wk.append(torch.nn.Parameter(torch.randn(n_embd, n_embd) * 0.08))
            self.attn_wv.append(torch.nn.Parameter(torch.randn(n_embd, n_embd) * 0.08))
            self.attn_wo.append(torch.nn.Parameter(torch.randn(n_embd, n_embd) * 0.08))
            self.mlp_gate.append(
                torch.nn.Parameter(torch.randn(self.intermediate_size, n_embd) * 0.08)
            )
            self.mlp_up.append(
                torch.nn.Parameter(torch.randn(self.intermediate_size, n_embd) * 0.08)
            )
            self.mlp_down.append(
                torch.nn.Parameter(torch.randn(n_embd, self.intermediate_size) * 0.08)
            )

        # RoPE precomputation (half-split style)
        head_dim = self.head_dim
        inv_freq = 1.0 / (
            10000.0 ** (torch.arange(0, head_dim, 2, dtype=torch.float) / head_dim)
        )
        pos = torch.arange(block_size, dtype=torch.float)
        freqs = pos[:, None] * inv_freq[None, :]  # (block_size, head_dim//2)
        self.cos_table = torch.cos(freqs)  # (block_size, head_dim//2)
        self.sin_table = torch.sin(freqs)  # (block_size, head_dim//2)

    @property
    def num_params(self) -> int:
        """Return the total number of trainable parameters.

        Returns
        -------
        int
            The sum of ``numel()`` across all parameters.
        """
        return sum(p.numel() for p in self.parameters())

    def parameters(self) -> Iterator[torch_Parameter]:
        """Yield all trainable parameters in the model.

        Iterates over all ``nn.Parameter`` and ``nn.ParameterList``
        attributes of the model.

        Yields
        ------
        torch.nn.Parameter
            Each trainable parameter in the model.
        """
        if not _TORCH_AVAILABLE:
            return
        assert torch is not None
        for v in vars(self).values():
            if isinstance(v, torch.nn.Parameter):
                yield v
            elif isinstance(v, torch.nn.ParameterList):
                yield from v

    def forward(
        self,
        token_id: int,
        pos_id: int,
        keys: list[list[torch_Tensor]],
        values: list[list[torch_Tensor]],
    ) -> torch_Tensor:
        """Run a single forward step through the transformer.

        Processes one token at the given position using PyTorch
        operations. This mirrors the architecture of
        ``anvil.core.engine.LlamaModel.forward`` but operates on
        PyTorch tensors with GPU support.

        Parameters
        ----------
        token_id : int
            The token index to embed.
        pos_id : int
            The position index for RoPE table lookup.
        keys : list of list
            Per-layer key cache (modified in-place).
        values : list of list
            Per-layer value cache (modified in-place).

        Returns
        -------
        torch.Tensor
            Logits over the vocabulary of shape ``(vocab_size,)``.
        """
        assert torch is not None
        assert F is not None
        # Token embedding only — NO wpe, NO embedding-level norm
        x = self.wte[token_id]

        for li in range(self.n_layer):
            x_residual = x

            # Pre-attention RMSNorm with learned scale
            x = (
                F.rms_norm(x, normalized_shape=(self.n_embd,), eps=1e-5)
                * self.rms_1[li]
            )

            q = F.linear(x, self.attn_wq[li])
            k = F.linear(x, self.attn_wk[li])
            v = F.linear(x, self.attn_wv[li])

            # Half-split RoPE: split each head's q/k into two halves and rotate
            half = self.head_dim // 2
            cos = self.cos_table[pos_id]  # (half,)
            sin = self.sin_table[pos_id]  # (half,)

            q_rot = torch.empty_like(q)
            k_rot = torch.empty_like(k)
            for h in range(self.n_head):
                hs = h * self.head_dim
                q_h = q[hs : hs + self.head_dim]
                k_h = k[hs : hs + self.head_dim]

                q1 = q_h[:half]
                q2 = q_h[half:]
                q_rot[hs : hs + self.head_dim] = torch.cat(
                    [q1 * cos - q2 * sin, q1 * sin + q2 * cos]
                )

                k1 = k_h[:half]
                k2 = k_h[half:]
                k_rot[hs : hs + self.head_dim] = torch.cat(
                    [k1 * cos - k2 * sin, k1 * sin + k2 * cos]
                )

            # Cache rotated k and v
            keys[li].append(k_rot)
            values[li].append(v)

            x_attn_parts = []
            for h in range(self.n_head):
                hs = h * self.head_dim
                q_h = q_rot[hs : hs + self.head_dim]

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

            # Pre-MLP RMSNorm with learned scale
            x_residual = x
            x = (
                F.rms_norm(x, normalized_shape=(self.n_embd,), eps=1e-5)
                * self.rms_2[li]
            )

            # SwiGLU MLP
            gate = F.silu(F.linear(x, self.mlp_gate[li]))
            up = F.linear(x, self.mlp_up[li])
            x = F.linear(gate * up, self.mlp_down[li])
            x = x + x_residual

        # Final RMSNorm with learned scale before lm_head
        x = F.rms_norm(x, normalized_shape=(self.n_embd,), eps=1e-5) * self.rms_final
        logits = cast(torch_Tensor, F.linear(x, self.lm_head))
        return logits

    def to(self, device: str | torch_device) -> TorchLlamaModel:
        """Move all model parameters and buffers to a device.

        Transfers ``nn.Parameter``, ``nn.ParameterList``, and RoPE
        buffer tensors (``cos_table``, ``sin_table``) to the given
        device.

        Parameters
        ----------
        device : torch.device or str
            Target device (e.g., ``"cpu"``, ``"cuda:0"``, ``"mps"``).

        Returns
        -------
        TorchLlamaModel
            ``self`` for method chaining.
        """
        assert torch is not None
        for v in vars(self).values():
            if isinstance(v, torch.nn.Parameter):
                v.data = v.data.to(device)
            elif isinstance(v, torch.nn.ParameterList):
                for p in v:
                    p.data = p.data.to(device)
        # Move RoPE buffer tensors (non-parameter tensors)
        self.cos_table = self.cos_table.to(device)
        self.sin_table = self.sin_table.to(device)
        return self

    def eval(self) -> None:
        """Set the model to evaluation mode.

        This is a no-op for the current implementation since dropout
        and batch norm are not used. Included for API compatibility
        with PyTorch conventions.
        """

    def export_weights(self) -> dict[str, list[Any]]:
        """Export all weights as plain Python lists.

        Detaches each parameter tensor, moves it to CPU, converts to
        a nested Python list, and returns a dictionary keyed by weight
        name (``wte``, ``lm_head``, ``layer{i}.attn_wq``, etc.).

        Returns
        -------
        dict of str to list
            A dictionary mapping weight names to their values as
            Python lists (2D matrices for weights, 1D vectors for
            RMSNorm scales).
        """
        assert torch is not None
        sd: dict[str, list[Any]] = {}
        sd["wte"] = self.wte.detach().cpu().tolist()
        sd["lm_head"] = self.lm_head.detach().cpu().tolist()
        sd["rms_final"] = self.rms_final.detach().cpu().tolist()

        for li in range(self.n_layer):
            sd[f"layer{li}.attn_wq"] = self.attn_wq[li].detach().cpu().tolist()
            sd[f"layer{li}.attn_wk"] = self.attn_wk[li].detach().cpu().tolist()
            sd[f"layer{li}.attn_wv"] = self.attn_wv[li].detach().cpu().tolist()
            sd[f"layer{li}.attn_wo"] = self.attn_wo[li].detach().cpu().tolist()
            sd[f"layer{li}.rms_1"] = self.rms_1[li].detach().cpu().tolist()
            sd[f"layer{li}.rms_2"] = self.rms_2[li].detach().cpu().tolist()
            sd[f"layer{li}.mlp_gate"] = self.mlp_gate[li].detach().cpu().tolist()
            sd[f"layer{li}.mlp_up"] = self.mlp_up[li].detach().cpu().tolist()
            sd[f"layer{li}.mlp_down"] = self.mlp_down[li].detach().cpu().tolist()

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
    progress_callback: Callable[..., None] | None = None,
    stop_check: Callable[[], bool] | None = None,
) -> tuple[dict[str, list[list[float]]], float, list[str], list[str]]:
    """Train a ``TorchLlamaModel`` on a list of documents using PyTorch.

    This is the GPU-accelerated training loop. It builds a character-
    level vocabulary, creates a ``TorchLlamaModel``, and runs Adam
    optimization with linear learning rate decay on the specified
    device (CPU, CUDA, or MPS). After training, generates 20 sample
    strings and exports the model weights.

    Parameters
    ----------
    docs : list of str
        Training documents.
    device : str, optional
        Device string (``"cpu"``, ``"cuda:0"``, ``"mps"``).
        Defaults to ``"cpu"``.
    num_steps : int, optional
        Number of training steps. Defaults to ``1000``.
    block_size : int, optional
        Context window size. Defaults to ``16``.
    n_embd : int, optional
        Embedding dimension. Defaults to ``16``.
    n_head : int, optional
        Number of attention heads. Defaults to ``4``.
    n_layer : int, optional
        Number of transformer layers. Defaults to ``1``.
    learning_rate : float, optional
        Peak learning rate. Defaults to ``0.01``.
    beta1 : float, optional
        Adam beta1. Defaults to ``0.85``.
    beta2 : float, optional
        Adam beta2. Defaults to ``0.99``.
    temperature : float, optional
        Sampling temperature. Defaults to ``0.5``.
    progress_callback : callable, optional
        Called after each step as ``progress_callback(step, loss)``.
    stop_check : callable, optional
        Called before each step. Returns ``True`` to halt early.

    Returns
    -------
    tuple
        A 4-tuple ``(exported_weights, final_loss, samples, uchars)``
        where ``exported_weights`` is the model state dict as plain
        Python lists, ``final_loss`` is the loss at the last step,
        ``samples`` are 20 generated strings, and ``uchars`` is the
        sorted character vocabulary.

    Raises
    ------
    RuntimeError
        If PyTorch is not installed.
    """
    if not _TORCH_AVAILABLE:
        msg = "torch is not installed — cannot run GPU training"
        raise RuntimeError(msg)
    assert torch is not None
    assert F is not None

    torch.manual_seed(42)
    device_obj = torch.device(device)

    uchars = sorted(set("".join(docs)))
    BOS = len(uchars)
    vocab_size = len(uchars) + 1

    model = TorchLlamaModel(vocab_size, n_embd, n_head, n_layer, block_size)
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

        keys: list[list[torch_Tensor]] = [[] for _ in range(n_layer)]
        values: list[list[torch_Tensor]] = [[] for _ in range(n_layer)]

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

        grad_sq = 0.0
        for p in model.parameters():
            if p.grad is not None:
                grad_sq += float(p.grad.detach().pow(2).sum().item())
        grad_norm = math.sqrt(grad_sq)

        optim.step()
        scheduler.step()

        loss_val = loss.item()
        final_loss_val = loss_val

        if progress_callback is not None:
            progress_callback(step, loss_val, tokens=n, grad_norm=grad_norm)

    samples: list[str] = []
    with torch.no_grad():
        for _ in range(20):
            token_id = BOS
            sample: list[str] = []
            samp_keys: list[list[torch_Tensor]] = [[] for _ in range(model.n_layer)]
            samp_values: list[list[torch_Tensor]] = [[] for _ in range(model.n_layer)]
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
