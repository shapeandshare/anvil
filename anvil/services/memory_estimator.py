"""Memory estimation for model training — pre-flight compute ceiling check.

Estimates GPU (or system) memory needed for a given model configuration
before training starts, so users can be warned before an OOM occurs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from anvil.gpu import GpuInfo, detect_gpu


# Bytes per float32
_FP32_BYTES = 4

# Safety margin: we warn if estimated peak exceeds this fraction of available memory
_WARN_THRESHOLD = 0.75
_BLOCK_THRESHOLD = 0.90


def _compute_param_count(vocab_size: int, n_embd: int, n_head: int, n_layer: int) -> int:
    """Calculate total trainable parameters for the Llama-like architecture.

    Matches the formula used in the frontend (training.html:updateModelStats).
    """
    intermediate = int(8 * n_embd / 3)
    # Embeddings
    wte = vocab_size * n_embd
    lm_head = vocab_size * n_embd
    rms_final = n_embd
    # Per layer
    attn_per_layer = 4 * n_embd * n_embd  # wq, wk, wv, wo
    mlp_per_layer = 3 * intermediate * n_embd  # gate, up, down
    rms_per_layer = 2 * n_embd  # rms_1, rms_2
    per_layer = attn_per_layer + mlp_per_layer + rms_per_layer
    return wte + lm_head + rms_final + n_layer * per_layer


@dataclass
class MemoryEstimate:
    """Detailed memory breakdown for a given model configuration."""

    # Model configuration
    vocab_size: int
    n_embd: int
    n_head: int
    n_layer: int
    block_size: int
    intermediate_size: int

    # Parameter counts
    param_count: int

    # Memory components (bytes)
    weights_bytes: int = 0       # Model parameters (fp32)
    gradients_bytes: int = 0     # Gradient storage (fp32)
    optimizer_bytes: int = 0     # Adam m + v (2 × fp32)
    kv_cache_bytes: int = 0      # KV cache per layer
    total_bytes: int = 0         # weights + gradients + optimizer + kv_cache
    peak_bytes: int = 0          # total × activation headroom (~2×)

    # Available resources
    available_bytes: int | None = None
    device_backend: str | None = None
    device_name: str | None = None

    # Warnings
    would_oom: bool | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def total_mb(self) -> float:
        return self.total_bytes / (1024**2)

    @property
    def peak_mb(self) -> float:
        return self.peak_bytes / (1024**2)

    @property
    def available_mb(self) -> float | None:
        if self.available_bytes is not None:
            return self.available_bytes / (1024**2)
        return None

    @property
    def peak_gb(self) -> float:
        return self.peak_bytes / (1024**3)

    @property
    def available_gb(self) -> float | None:
        if self.available_bytes is not None:
            return self.available_bytes / (1024**3)
        return None

    @property
    def utilization_pct(self) -> float | None:
        """Percentage of available memory the peak estimate consumes."""
        if self.available_bytes and self.available_bytes > 0:
            return (self.peak_bytes / self.available_bytes) * 100
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "vocab_size": self.vocab_size,
            "n_embd": self.n_embd,
            "n_layer": self.n_layer,
            "n_head": self.n_head,
            "block_size": self.block_size,
            "intermediate_size": self.intermediate_size,
            "param_count": self.param_count,
            "param_count_formatted": _format_count(self.param_count),
            "weights_mb": round(self.weights_bytes / (1024**2), 1),
            "gradients_mb": round(self.gradients_bytes / (1024**2), 1),
            "optimizer_mb": round(self.optimizer_bytes / (1024**2), 1),
            "kv_cache_mb": round(self.kv_cache_bytes / (1024**2), 1),
            "total_mb": round(self.total_mb, 1),
            "peak_mb": round(self.peak_mb, 1),
            "available_mb": round(self.available_mb, 1) if self.available_mb is not None else None,
            "available_gb": round(self.available_gb, 1) if self.available_gb is not None else None,
            "device_backend": self.device_backend,
            "device_name": self.device_name,
            "would_oom": self.would_oom,
            "utilization_pct": round(self.utilization_pct, 1) if self.utilization_pct is not None else None,
            "warnings": self.warnings,
        }


def _format_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def estimate_training_memory(
    vocab_size: int,
    n_embd: int = 16,
    n_head: int = 4,
    n_layer: int = 1,
    block_size: int = 16,
    use_gpu: bool = False,
    gpu_info: GpuInfo | None = None,
) -> MemoryEstimate:
    """Estimate peak memory usage for a training run with the given config.

    Args:
        vocab_size: Vocabulary size (characters + BOS).
        n_embd: Embedding dimension.
        n_head: Number of attention heads.
        n_layer: Number of transformer layers.
        block_size: Context window (sequence length).
        use_gpu: Whether GPU training is requested.
        gpu_info: Pre-detected GPU info, or None to auto-detect.

    Returns:
        A MemoryEstimate dataclass with breakdown and OOM prediction.
    """
    intermediate = int(8 * n_embd / 3)
    param_count = _compute_param_count(vocab_size, n_embd, n_head, n_layer)

    # Memory for fp32 training (both stdlib and torch use fp32 internally)
    weights = param_count * _FP32_BYTES
    gradients = param_count * _FP32_BYTES
    optimizer = param_count * _FP32_BYTES * 2  # Adam: m + v

    # KV cache: n_layer × 2 (K+V) × block_size × n_embd × fp32
    kv_cache = n_layer * 2 * block_size * n_embd * _FP32_BYTES

    total = weights + gradients + optimizer + kv_cache

    # Peak: during backward pass, activations add significant overhead.
    # A conservative rule of thumb is ~2× total for the backward pass.
    # For the stdlib engine with Value objects, actual overhead is higher,
    # but we use fp32 estimates since that's the bottleneck on GPU.
    peak = int(total * 2)

    # Detect GPU if not provided
    if gpu_info is None and use_gpu:
        gpu_info = detect_gpu()

    available = None
    device_backend = None
    device_name = None
    would_oom = None
    warnings: list[str] = []

    if use_gpu and gpu_info and gpu_info.available:
        device_backend = gpu_info.backend
        device_name = gpu_info.device_name

        if gpu_info.backend == "cuda" and gpu_info.memory_available_gb is not None:
            available = int(gpu_info.memory_available_gb * (1024**3))
        elif gpu_info.memory_total_gb is not None:
            # MPS: use total system memory as ceiling
            available = int(gpu_info.memory_total_gb * (1024**3))
        else:
            warnings.append("Could not determine available GPU memory")

        if available is not None and available > 0:
            utilization = peak / available
            if utilization >= _BLOCK_THRESHOLD:
                would_oom = True
                warnings.append(
                    f"Estimated peak memory ({peak / (1024**3):.1f} GB) exceeds "
                    f"{_BLOCK_THRESHOLD * 100:.0f}% of available memory "
                    f"({available / (1024**3):.1f} GB) — training will likely OOM"
                )
            elif utilization >= _WARN_THRESHOLD:
                would_oom = False
                warnings.append(
                    f"Estimated peak memory ({peak / (1024**3):.1f} GB) uses "
                    f"{utilization * 100:.0f}% of available memory "
                    f"({available / (1024**3):.1f} GB) — close to limit"
                )
            else:
                would_oom = False
        else:
            warnings.append("GPU available but memory info not available — cannot estimate")
    elif use_gpu:
        warnings.append("GPU requested but not available — will fall back to CPU")
    else:
        # CPU mode: less likely to OOM (slower but uses virtual memory)
        would_oom = False
        warnings.append("CPU training — memory ceiling determined by system RAM")

    return MemoryEstimate(
        vocab_size=vocab_size,
        n_embd=n_embd,
        n_head=n_head,
        n_layer=n_layer,
        block_size=block_size,
        intermediate_size=intermediate,
        param_count=param_count,
        weights_bytes=weights,
        gradients_bytes=gradients,
        optimizer_bytes=optimizer,
        kv_cache_bytes=kv_cache,
        total_bytes=total,
        peak_bytes=peak,
        available_bytes=available,
        device_backend=device_backend,
        device_name=device_name,
        would_oom=would_oom,
        warnings=warnings,
    )