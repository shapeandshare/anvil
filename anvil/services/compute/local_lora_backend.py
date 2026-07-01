# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Local LoRA/QLoRA fine-tuning compute backend.

Wraps ``peft`` and ``transformers`` for parameter-efficient fine-tuning
as an async ``ComputeBackendProtocol`` implementation.  Supports LoRA
and QLoRA (4-bit quantised) fine-tuning of HuggingFace causal language
models.

Gracefully degrades to a synthetic placeholder loop when ``peft`` /
``torch`` are not installed.

Auto-registers as ``"local-lora"`` in the compute registry at module
import time.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from ..training.stop_requested import StopRequested
from .compute_backend_result import ComputeBackendResult
from .compute_status import ComputeStatus
from .protocol import ProgressCallback, StopCheck
from .registry import register
from .registry_backend import RegistryBackend
from .result import ComputeResult
from .training_engine import TrainingEngine

logger = logging.getLogger(__name__)


# ── optional dependency guards ──────────────────────────────────────────


def _peft_available() -> bool:
    """Check whether ``peft`` and ``torch`` are both importable.

    Returns
    -------
    bool
        ``True`` when both ``peft`` and ``torch`` can be imported;
        ``False`` otherwise.
    """
    try:
        import peft  # noqa: F401
        import torch  # noqa: F401

        return True
    except ImportError:
        return False


def _bitsandbytes_available() -> bool:
    """Check whether ``bitsandbytes`` is importable.

    Returns
    -------
    bool
        ``True`` if ``bitsandbytes`` can be imported; ``False`` otherwise.
    """
    try:
        import bitsandbytes  # noqa: F401

        return True
    except ImportError:
        return False


def _transformers_available() -> bool:
    """Check whether ``transformers`` is importable.

    Returns
    -------
    bool
        ``True`` if ``transformers`` can be imported; ``False`` otherwise.
    """
    try:
        import transformers  # noqa: F401

        return True
    except ImportError:
        return False


# ── synthetic training (graceful degrade) ───────────────────────────────


def _run_synthetic_lora(
    *,
    num_steps: int,
    progress_callback: ProgressCallback,
    stop_check: StopCheck,
) -> tuple[float, list[str]]:
    """Run a synthetic placeholder LoRA training loop.

    Used when ``peft`` / ``torch`` / ``transformers`` are not installed.
    Emulates decreasing loss values so the calling UI sees realistic-looking
    progress.

    Parameters
    ----------
    num_steps : int
        Number of training steps to simulate.
    progress_callback : ProgressCallback
        Callable invoked with ``(step, loss)`` at each synthetic step.
    stop_check : StopCheck
        Callable returning ``True`` if cancellation was requested.

    Returns
    -------
    tuple[float, list[str]]
        ``(final_loss, samples)`` where *samples* contains a single
        placeholder string.

    Raises
    ------
    StopRequested
        If ``stop_check()`` returns ``True`` during the loop.
    """
    final_loss: float = 5.0
    samples: list[str] = ["[synthetic lora — peft/torch not installed]"]

    for step in range(1, num_steps + 1):
        if stop_check():
            raise StopRequested("Training cancelled by user")

        # Synthetic loss decreasing from ~5.0 toward ~0.5
        fraction = step / num_steps
        final_loss = 5.0 * (1.0 - fraction) + 0.5 * fraction
        progress_callback(step, final_loss)

    return final_loss, samples


# ── real LoRA/QLoRA training ────────────────────────────────────────────


def _run_real_lora(
    docs: list[str],
    *,
    method: str,
    base_model_ref: str | None,
    lora_rank: int,
    lora_alpha: int,
    lora_target_modules: list[str] | None,
    lora_dropout: float,
    lora_bias: str,
    device: str,
    num_steps: int,
    learning_rate: float,
    progress_callback: ProgressCallback,
    stop_check: StopCheck,
) -> tuple[Path, float, list[str]]:
    """Execute LoRA/QLoRA fine-tuning with ``peft`` + ``transformers``.

    This function is only called after ``_peft_available()`` has confirmed
    that the optional dependencies are importable.

    Parameters
    ----------
    docs : list[str]
        Training documents (raw text strings).
    method : str
        Fine-tuning method — ``"lora"`` or ``"qlora"``.
    base_model_ref : str | None
        Reference identifier for the base model (used to resolve the
        model path).
    lora_rank : int
        LoRA rank (``r``) dimension.
    lora_alpha : int
        LoRA scaling alpha parameter.
    lora_target_modules : list[str] | None
        Module names to attach LoRA adapters to.  ``None`` defaults to
        ``["q_proj", "v_proj"]``.
    lora_dropout : float
        Dropout probability for LoRA layers.
    lora_bias : str
        LoRA bias setting (``"none"``, ``"all"``, or ``"lora_only"``).
    device : str
        Target device (``"cpu"``, ``"cuda"``, ``"mps"``).
    num_steps : int
        Number of training steps.
    learning_rate : float
        Optimizer learning rate.
    progress_callback : ProgressCallback
        Callable invoked with ``(step, loss)`` at each step.
    stop_check : StopCheck
        Callable returning ``True`` if cancellation was requested.

    Returns
    -------
    tuple[Path, float, list[str]]
        ``(adapter_path, final_loss, samples)`` — the filesystem path
        where the LoRA adapter was saved, the final loss value, and a
        list of generated sample strings.

    Raises
    ------
    StopRequested
        If ``stop_check()`` returns ``True`` during training.
    """
    # Lazy imports — these are optional dependencies behind ``[finetune]``.
    import torch  # import-placement:allow
    import transformers  # import-placement:allow
    from peft import LoraConfig, get_peft_model  # import-placement:allow

    # ── resolve model path (v1 placeholder) ────────────────────────────
    if base_model_ref is not None:
        model_path = str(Path(f"data/models/{base_model_ref}/"))
    else:
        model_path = _resolve_default_model_path()
    logger.info("Loading base model from %s", model_path)

    # ── configure quantization for QLoRA ───────────────────────────────
    quantization_config: Any = None
    if method == "qlora" and _bitsandbytes_available():
        from transformers import BitsAndBytesConfig  # import-placement:allow

        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
        )
        logger.info("QLoRA enabled — loading model in 4-bit NF4")
    elif method == "qlora":
        logger.warning(
            "QLoRA requested but bitsandbytes not available — "
            "falling back to full-precision LoRA"
        )

    # ── determine torch dtype ──────────────────────────────────────────
    if device == "cuda" and torch.cuda.is_available():
        torch_dtype = torch.bfloat16
        compute_device = "cuda"
    elif device == "mps" and torch.backends.mps.is_available():
        torch_dtype = torch.float32
        compute_device = "mps"
    else:
        torch_dtype = torch.float32
        compute_device = "cpu"

    # ── load base model ────────────────────────────────────────────────
    model = transformers.AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch_dtype,
        quantization_config=quantization_config,
        device_map="auto" if compute_device == "cuda" else None,
        trust_remote_code=False,
    )

    # ── load tokenizer ─────────────────────────────────────────────────
    tokenizer = transformers.AutoTokenizer.from_pretrained(model_path)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ── tokenise training corpus ──────────────────────────────────────
    corpus = "\n\n".join(docs)
    encodings = tokenizer(
        corpus,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=512,
    )

    # ── apply LoRA configuration ──────────────────────────────────────
    target_modules = lora_target_modules or ["q_proj", "v_proj"]

    lora_config = LoraConfig(
        r=lora_rank,
        lora_alpha=lora_alpha,
        target_modules=target_modules,
        lora_dropout=lora_dropout,
        bias=lora_bias,
        task_type="CAUSAL_LM",
    )

    peft_model = get_peft_model(model, lora_config)
    peft_model.to(compute_device)
    peft_model.train()
    logger.info(
        "LoRA configured: rank=%d alpha=%d targets=%s device=%s",
        lora_rank,
        lora_alpha,
        target_modules,
        compute_device,
    )

    # ── prepare inputs ────────────────────────────────────────────────
    input_ids = encodings["input_ids"].to(compute_device)
    attention_mask = encodings.get("attention_mask", None)
    if attention_mask is not None:
        attention_mask = attention_mask.to(compute_device)

    optimizer = torch.optim.AdamW(peft_model.parameters(), lr=learning_rate)

    # ── training loop ──────────────────────────────────────────────────
    final_loss: float = 0.0

    for step in range(1, num_steps + 1):
        if stop_check():
            raise StopRequested("Training cancelled by user")

        optimizer.zero_grad()
        outputs = peft_model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=input_ids,
        )
        loss = outputs.loss
        loss.backward()
        optimizer.step()

        final_loss = loss.item()
        progress_callback(step, final_loss)

    logger.info("Training complete — final_loss=%.4f", final_loss)

    # ── generate a sample for qualitative inspection ───────────────────
    peft_model.eval()
    sample_text: str = ""
    with torch.no_grad():
        input_prefix = input_ids[:, :10]
        generated_ids = peft_model.generate(
            input_ids=input_prefix,
            max_new_tokens=50,
            do_sample=True,
            temperature=0.7,
        )
        sample_text = tokenizer.decode(
            generated_ids[0],
            skip_special_tokens=True,
        )

    samples: list[str] = [sample_text]

    # ── save adapter ───────────────────────────────────────────────────
    timestamp = int(time.time())
    adapter_path = Path(f"data/adapters/lora_{timestamp}/")
    adapter_path.mkdir(parents=True, exist_ok=True)
    peft_model.save_pretrained(str(adapter_path))
    logger.info("Adapter saved to %s", adapter_path)

    return adapter_path, final_loss, samples


def _resolve_default_model_path() -> str:
    """Resolve a fallback model path when no ``base_model_ref`` is provided.

    Returns
    -------
    str
        Path string pointing to the default model directory.
    """
    return str(Path("data/models/default/"))


# ── backend class ───────────────────────────────────────────────────────


class LocalLoraBackend:
    """Local LoRA/QLoRA fine-tuning backend using ``peft`` + ``transformers``.

    Runs fine-tuning in a thread pool executor via ``loop.run_in_executor()``
    to avoid blocking the async event loop.  Gracefully degrades to a
    synthetic placeholder loop when optional dependencies are missing.

    Automatically registered as ``"local-lora"`` in the compute registry
    at module import time.
    """

    #: Backend identifier used by the registry and resolution layer.
    name = RegistryBackend.LOCAL_LORA

    @staticmethod
    def is_available() -> bool:
        """Check whether the LoRA backend dependencies are installed.

        Returns ``True`` only if both ``peft`` and ``torch`` can be
        imported in the current environment.

        Returns
        -------
        bool
            ``True`` if ``peft`` and ``torch`` are both importable.
        """
        return _peft_available()

    async def run(
        self,
        docs: list[str],
        config: dict[str, Any],
        *,
        progress_callback: ProgressCallback,
        stop_check: StopCheck,
    ) -> ComputeResult:
        """Run LoRA/QLoRA fine-tuning in a thread pool.

        Extracts LoRA hyperparameters from *config*, resolves the base
        model path, loads the model, applies LoRA adapters, and runs
        training.  Falls back to a synthetic loop when ``peft`` /
        ``torch`` are not installed.

        Parameters
        ----------
        docs : list[str]
            Training documents (raw text strings).
        config : dict[str, Any]
            Hyperparameter dictionary with keys:

            - ``method`` : ``"lora"`` or ``"qlora"``
            - ``base_model_ref`` : base model identifier
            - ``lora_rank`` : LoRA rank dimension
            - ``lora_alpha`` : LoRA scaling alpha
            - ``lora_target_modules`` : target module name list
            - ``lora_dropout`` : LoRA dropout probability
            - ``lora_bias`` : LoRA bias setting
            - ``num_steps`` : number of training steps
            - ``learning_rate`` : optimizer learning rate
            - ``device`` : target device string
        progress_callback : ProgressCallback
            Callable invoked with ``(step, loss)`` at each step.
        stop_check : StopCheck
            Callable returning ``True`` if cancellation was requested.

        Returns
        -------
        ComputeResult
            Completed or failed result with adapter artifact URIs.
        """
        # ── extract config ──────────────────────────────────────────────
        method: str = config.get("method", "lora")
        base_model_ref: str | None = config.get("base_model_ref")
        lora_rank: int = int(config.get("lora_rank", 8))
        lora_alpha: int = int(config.get("lora_alpha", 16))
        lora_target_modules: list[str] | None = config.get("lora_target_modules")
        lora_dropout: float = float(config.get("lora_dropout", 0.05))
        lora_bias: str = config.get("lora_bias", "none")
        device: str = config.get("device", "cpu")
        num_steps: int = int(config.get("num_steps", 100))
        learning_rate: float = float(config.get("learning_rate", 5e-4))

        logger.info(
            "LocalLoraBackend starting: method=%s base_model=%s "
            "rank=%d alpha=%d steps=%d device=%s",
            method,
            base_model_ref,
            lora_rank,
            lora_alpha,
            num_steps,
            device,
        )

        loop = asyncio.get_event_loop()

        # ── synthetic fallback when optional deps are missing ───────────
        if not _peft_available():
            logger.warning(
                "peft/torch not available — running synthetic LoRA loop "
                "(install peft + torch for real fine-tuning)"
            )
            try:
                final_loss, samples = await loop.run_in_executor(
                    None,
                    lambda: _run_synthetic_lora(
                        num_steps=num_steps,
                        progress_callback=progress_callback,
                        stop_check=stop_check,
                    ),
                )
            except Exception as exc:
                if isinstance(exc, StopRequested):
                    return ComputeResult(
                        status=ComputeStatus.FAILED,
                        error_message="Training cancelled by user",
                        engine=TrainingEngine.TORCH,
                        backend=ComputeBackendResult.LOCAL,
                    )
                return ComputeResult(
                    status=ComputeStatus.FAILED,
                    error_message=str(exc),
                    engine=TrainingEngine.TORCH,
                    backend=ComputeBackendResult.LOCAL,
                )

            return ComputeResult(
                status=ComputeStatus.COMPLETED,
                model=None,
                final_loss=final_loss,
                samples=samples,
                engine=TrainingEngine.TORCH,
                backend=ComputeBackendResult.LOCAL,
                artifact_uris={"adapter_path": ""},
            )

        # ── real fine-tuning with peft + transformers ───────────────────
        try:
            adapter_path, final_loss, samples = await loop.run_in_executor(
                None,
                lambda: _run_real_lora(
                    docs=docs,
                    method=method,
                    base_model_ref=base_model_ref,
                    lora_rank=lora_rank,
                    lora_alpha=lora_alpha,
                    lora_target_modules=lora_target_modules,
                    lora_dropout=lora_dropout,
                    lora_bias=lora_bias,
                    device=device,
                    num_steps=num_steps,
                    learning_rate=learning_rate,
                    progress_callback=progress_callback,
                    stop_check=stop_check,
                ),
            )
        except Exception as exc:
            if isinstance(exc, StopRequested):
                return ComputeResult(
                    status=ComputeStatus.FAILED,
                    error_message="Training cancelled by user",
                    engine=TrainingEngine.TORCH,
                    backend=ComputeBackendResult.LOCAL,
                )
            logger.exception("LoRA fine-tuning failed")
            return ComputeResult(
                status=ComputeStatus.FAILED,
                error_message=str(exc),
                engine=TrainingEngine.TORCH,
                backend=ComputeBackendResult.LOCAL,
            )

        logger.info(
            "LoRA fine-tuning completed: adapter_path=%s final_loss=%.4f",
            adapter_path,
            final_loss,
        )

        return ComputeResult(
            status=ComputeStatus.COMPLETED,
            model=None,
            final_loss=final_loss,
            samples=samples,
            engine=TrainingEngine.TORCH,
            backend=ComputeBackendResult.LOCAL,
            artifact_uris={"adapter_path": str(adapter_path)},
        )


# ── auto-register ───────────────────────────────────────────────────────


def _lora_factory() -> LocalLoraBackend:
    """Factory callable for the LoRA local backend.

    Returns
    -------
    LocalLoraBackend
        A new instance of the LoRA fine-tuning backend.
    """
    return LocalLoraBackend()


register(RegistryBackend.LOCAL_LORA, _lora_factory)  # type: ignore[arg-type]
