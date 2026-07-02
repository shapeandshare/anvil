"""Adapter merge service — merges LoRA adapters into base model weights.

Provides the ``AdapterMergeService`` for merging a LoRA adapter into its
base model, producing a standalone model artifact with no adapter
dependency.  The ``merge()`` method is non-destructive (adapter files
are preserved); ``merge_and_export()`` performs the full pipeline
including safetensors conversion, atomic publish, and optional MLflow
lineage registration.

The pipeline uses **direct HuggingFace save** — the merged model is saved
via ``merged.save_pretrained()`` and the real subword tokenizer via
``AutoTokenizer.save_pretrained()``.  No anvil-internal ``LlamaModel``
round-trip is performed, avoiding the ``intermediate_size`` / ``chars``
loss-of-information bug.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ...db.models.external_model import ExternalModel
from ...db.repositories.external_models import ExternalModelRepository
from ...db.repositories.lora_adapter_repository import LoRAAdapterRepository
from ...storage.local import LocalFileStore
from ..tracking.tracking import TrackingService

try:
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    _MERGE_DEPS_AVAILABLE = True
except ImportError:
    _MERGE_DEPS_AVAILABLE = False

logger = logging.getLogger(__name__)

# ── Path sanitisation ────────────────────────────────────────────────────


def _safe_path_component(name: str, max_len: int = 128) -> str:
    """Sanitise a user-controlled string for safe use as a filesystem component.

    Allows only ``[a-zA-Z0-9._-]`` and truncates to *max_len*.
    Raises ``ValueError`` if the result is empty after sanitisation.

    Parameters
    ----------
    name : str
        The raw string (e.g. ``adapter_id``).
    max_len : int
        Maximum length of the sanitised component (default ``128``).

    Returns
    -------
    str
        Safe path component.
    """
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", name)[:max_len]
    if not safe:
        raise ValueError(f"Path component {name!r} is empty after sanitisation")
    return safe


# ── License restrictions ─────────────────────────────────────────────

# SPDX identifiers that prohibit redistribution (non-commercial,
# no-derivatives, or other restrictive variants).
_RESTRICTED_LICENSES: frozenset[str] = frozenset(
    {
        "cc-by-nc-4.0",
        "cc-by-nc-sa-4.0",
        "cc-by-nc-nd-4.0",
        "cc-by-nd-4.0",
        "cc-by-nc-3.0",
        "cc-by-nc-sa-3.0",
        "cc-by-nc-nd-3.0",
        "cc-by-nd-3.0",
        "odbl",
        "unknown",
    }
)


class AdapterMergeService:
    """Merge a LoRA adapter into its base model to create standalone weights.

    Parameters
    ----------
    lora_adapter_repo : LoRAAdapterRepository
        Repository for adapter CRUD operations.
    store : LocalFileStore
        File store for reading adapter artifacts and writing merged output.
    tracking : TrackingService | None
        Optional tracking service for MLflow lineage registration.
    external_model_repo : ExternalModelRepository | None
        Optional repository for resolving the base model path and
        performing license checks.
    """

    def __init__(
        self,
        lora_adapter_repo: LoRAAdapterRepository,
        store: LocalFileStore,
        tracking: TrackingService | None = None,
        external_model_repo: ExternalModelRepository | None = None,
    ) -> None:
        self._repo = lora_adapter_repo
        self._store = store
        self._tracking = tracking
        self._external_model_repo = external_model_repo

    # ── Public API ───────────────────────────────────────────────────

    async def merge(
        self,
        model_id: int,
        adapter_id: str,
    ) -> str:
        """Merge a LoRA adapter into its base model (non-destructive).

        Loads the adapter, calls ``PeftModel.merge_and_unload()`` to
        produce standalone weights, and saves the merged artifact.
        The original adapter files are **preserved** and ``merged_at``
        is **not** set — use ``merge_and_export()`` for the full
        lifecycle including lineage and atomic publish.

        Parameters
        ----------
        model_id : int
            FK to ``ExternalModel``.
        adapter_id : str
            The adapter's scoped identifier (e.g. ``"run_42"``).

        Returns
        -------
        str
            The storage path of the merged artifact.

        Raises
        ------
        ValueError
            If the adapter is not found.
        RuntimeError
            If ``peft`` / ``transformers`` packages are not installed,
            or the base model cannot be resolved.
        """
        adapter = await self._repo.get_by_adapter_id(model_id, adapter_id)
        if adapter is None:
            raise ValueError(f"Adapter {adapter_id!r} not found for model {model_id}")

        if not _MERGE_DEPS_AVAILABLE:
            raise RuntimeError(
                "Adapter merge requires peft, torch, and transformers. "
                "Install: pip install anvil[finetune]"
            )

        source_identifier = await self._resolve_source_identifier(model_id)

        safe_model_id = str(_safe_path_component(str(model_id)))
        safe_adapter_id = _safe_path_component(adapter_id)
        merged_path = f"models/{safe_model_id}/merged/{safe_adapter_id}/"

        base_model = AutoModelForCausalLM.from_pretrained(
            source_identifier,
            trust_remote_code=False,
        )
        adapter_model = PeftModel.from_pretrained(base_model, adapter.storage_path)
        merged = adapter_model.merge_and_unload()

        merged.save_pretrained(str(Path(f"data/storage/{merged_path}")))
        logger.info(
            "Merged adapter %s/%s -> %s (adapter files preserved)",
            model_id,
            adapter_id,
            merged_path,
        )

        return merged_path

    @staticmethod
    def _merge_hf_weights(
        source_identifier: str,
        adapter: Any,
        model_id: int,
        adapter_id: str,
    ) -> Any | dict[str, str]:
        """Merge adapter weights into the base HF model.

        Returns the merged model on success, or an ``{"error": ...}``
        dict on failure.
        """
        try:
            base_model = AutoModelForCausalLM.from_pretrained(
                source_identifier,
                trust_remote_code=False,
            )
            adapter_model = PeftModel.from_pretrained(base_model, adapter.storage_path)
            return adapter_model.merge_and_unload()
        except Exception as exc:
            msg = (
                f"Merge failed for adapter {adapter_id!r} on model {model_id}. "
                f"If the base model uses quantized weights (QLoRA), note that "
                f"``merge_and_unload()`` dequantizes to full precision, which "
                f"requires sufficient memory. Original error: {exc}"
            )
            logger.exception(msg)
            return {"error": msg}

    @staticmethod
    def _publish_artifact(
        merged_hf: Any,
        source_identifier: str,
        model_id: int,
        adapter_id: str,
    ) -> Path | dict[str, str]:
        """Export the merged HF model and publish atomically.

        Returns the final path on success, or an ``{"error": ...}``
        dict on failure.
        """
        safe_model_id = str(_safe_path_component(str(model_id)))
        safe_adapter_id = _safe_path_component(adapter_id)
        final_path = Path(
            f"data/storage/models/{safe_model_id}/merged/{safe_adapter_id}/"
        )
        tmp_dir: str | None = None

        try:
            tmp_dir = str(final_path.parent / f".{safe_adapter_id}.tmp-{uuid4().hex}")
            tmp_path = Path(tmp_dir)
            tmp_path.mkdir(parents=True, exist_ok=True)

            merged_hf.save_pretrained(tmp_path)

            try:
                tokenizer = AutoTokenizer.from_pretrained(source_identifier)
                tokenizer.save_pretrained(tmp_path)
            except Exception:
                logger.warning(
                    "Could not save tokenizer for %s; continuing without one",
                    source_identifier,
                )

            if final_path.exists():
                backup = final_path.parent / f".{safe_adapter_id}.bak-{uuid4().hex}"
                os.replace(str(final_path), str(backup))
                try:
                    os.replace(str(tmp_path), str(final_path))
                    shutil.rmtree(str(backup), ignore_errors=True)
                except Exception:
                    os.replace(str(backup), str(final_path))
                    raise
            else:
                final_path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(str(tmp_path), str(final_path))

            tmp_dir = None
            logger.info(
                "Merge+export complete for adapter %s/%s -> %s",
                model_id,
                adapter_id,
                final_path,
            )
            return final_path
        except Exception as exc:
            msg = f"Export failed after merge: {exc}"
            logger.exception(msg)
            return {"error": msg}
        finally:
            if tmp_dir is not None:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    async def merge_and_export(
        self,
        model_id: int,
        adapter_id: str,
    ) -> dict[str, Any]:
        """Merge, export, and register lineage for a LoRA adapter.

        Performs a license check, merges adapter weights into the base
        model, exports directly to HuggingFace format (safetensors +
        config + tokenizer), publishes the artifact atomically, and
        optionally registers MLflow lineage.  The original adapter
        files are **preserved**.

        Parameters
        ----------
        model_id : int
            FK to ``ExternalModel``.
        adapter_id : str
            The adapter's scoped identifier (e.g. ``"run_42"``).

        Returns
        -------
        dict
            ``{"path": ..., "lineage": ...}`` on success, or
            ``{"error": ...}`` on failure.

        Raises
        ------
        ValueError
            If the adapter is not found or license is restricted.
        RuntimeError
            If ``peft`` / ``transformers`` packages are not installed.
        """
        adapter = await self._repo.get_by_adapter_id(model_id, adapter_id)
        if adapter is None:
            msg = f"Adapter {adapter_id!r} not found for model {model_id}"
            logger.error(msg)
            return {"error": msg}
        if adapter.merged_at is not None:
            msg = f"Adapter {adapter_id!r} for model {model_id} is already merged"
            logger.warning(msg)
            return {"error": msg}

        # ── License check ────────────────────────────────────────────
        license_ok, license_msg = await self._check_license(model_id)
        if not license_ok:
            logger.error("License check failed for model %s: %s", model_id, license_msg)
            return {"error": license_msg}

        if not _MERGE_DEPS_AVAILABLE:
            msg = (
                "Adapter merge requires peft, torch, and transformers. "
                "Install: pip install anvil[finetune]"
            )
            return {"error": msg}

        try:
            source_identifier = await self._resolve_source_identifier(model_id)
        except RuntimeError as exc:
            return {"error": str(exc)}

        # ── Merge weights ────────────────────────────────────────────
        merged_hf = self._merge_hf_weights(source_identifier, adapter, model_id, adapter_id)
        if isinstance(merged_hf, dict):
            return merged_hf  # error dict

        # ── Export directly to HF format ─────────────────────────
        result = self._publish_artifact(
            merged_hf, source_identifier, model_id, adapter_id,
        )
        if isinstance(result, dict):
            return result
        final_path = result

        # ── MLflow lineage registration ───────────────────
        if self._tracking is not None:
            try:
                lineage_result = await self._register_lineage(
                    model_id=model_id,
                    adapter_id=adapter_id,
                    adapter_method=adapter.method,
                    export_dir=str(final_path),
                )
            except Exception as exc:
                logger.warning("Lineage registration failed: %s", exc)
                lineage_result = {"registered": False, "error": str(exc)}
        else:
            lineage_result = {"registered": False, "error": "No tracking service"}

        if lineage_result.get("registered"):
            updated = await self._repo.mark_merged(model_id, adapter_id)
            if updated is None:
                msg = f"Failed to mark adapter {adapter_id!r} as merged"
                logger.error(msg)
                return {"error": msg}
        else:
            shutil.rmtree(str(final_path), ignore_errors=True)
            err = lineage_result.get("error", "Lineage registration failed")
            logger.error("Lineage failure for %s/%s: %s", model_id, adapter_id, err)
            return {"error": err}

        return {
            "path": str(final_path),
            "lineage": lineage_result,
        }

    # ── Internal helpers ─────────────────────────────────────────────

    async def _resolve_source_identifier(self, model_id: int) -> str:
        """Resolve the HuggingFace source identifier for a base model.

        Parameters
        ----------
        model_id : int
            FK to ``ExternalModel``.

        Returns
        -------
        str
            The ``source_identifier`` (e.g. ``"meta-llama/Llama-2-7b"``).

        Raises
        ------
        RuntimeError
            If the model cannot be resolved.
        """
        if self._external_model_repo is None:
            raise RuntimeError(
                f"Cannot resolve base model {model_id}: no ExternalModelRepository"
            )
        model: ExternalModel | None = await self._external_model_repo.get(model_id)
        if model is None:
            raise RuntimeError(f"External model {model_id!r} not found")
        return model.source_identifier

    async def _check_license(self, model_id: int) -> tuple[bool, str]:
        """Verify that the base model's license allows redistribution.

        Parameters
        ----------
        model_id : int
            FK to ``ExternalModel``.

        Returns
        -------
        tuple[bool, str]
            ``(True, "")`` if the license is permissive, or
            ``(False, "descriptive error message")`` if restricted.
        """
        if self._external_model_repo is None:
            return True, ""

        model: ExternalModel | None = await self._external_model_repo.get(model_id)
        if model is None:
            return False, f"External model {model_id!r} not found for license check"

        spdx = (model.license or "").strip().lower()
        if spdx in _RESTRICTED_LICENSES:
            return (
                False,
                f"Base model (id={model_id}) has license '{model.license}' "
                f"which restricts redistribution. Merge+export is blocked. "
                f"If you believe this is an error, please verify the SPDX "
                f"identifier in the model registry.",
            )
        return True, ""

    async def _register_lineage(
        self,
        model_id: int,
        adapter_id: str,
        adapter_method: str,
        export_dir: str,
    ) -> dict[str, Any]:
        """Register MLflow lineage tags for a completed merge.

        Logs the exported artifact directory to the run, then registers
        the model source so the registry points at a real artifact.

        Parameters
        ----------
        model_id : int
            Base model ID.
        adapter_id : str
            Adapter identifier.
        adapter_method : str
            Fine-tuning method (``"lora"`` or ``"qlora"``).
        export_dir : str
            Path to the exported artifact directory to log.

        Returns
        -------
        dict
            Registration result from the tracking service.
        """
        tracking = self._tracking
        if tracking is None:
            return {"registered": False, "error": "No tracking service"}

        run_id = await tracking.start_run(
            run_name=f"merge-{adapter_id}",
            engine_backend="merge",
            device="n/a",
        )
        if not run_id:
            return {"registered": False, "error": "Failed to create MLflow run"}

        await tracking.log_artifact_dir(run_id, export_dir)

        result = await tracking.register_source_model(
            run_id=run_id,
            name=f"adapter-merge-{adapter_id}",
            artifact_path="",
        )

        tags: dict[str, str] = {
            "anvil.origin": "merge",
            "anvil.base_model_ref": str(model_id),
            "anvil.adapter_id": adapter_id,
            "anvil.merge_timestamp": datetime.now(UTC).isoformat(),
            "anvil.method": adapter_method,
        }
        for key, value in tags.items():
            await tracking.set_tag(run_id, key, value)

        await tracking.finish_run(run_id)

        return {
            "registered": True,
            "registry_name": result.get("name", ""),
            "registry_version": result.get("version", ""),
            "run_id": run_id,
        }
