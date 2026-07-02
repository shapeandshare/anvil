"""Service for persisting ``LoRAAdapter`` rows after fine-tuning completion.

Fixes the pre-existing gap (047 Phase 2) where ``LocalLoraBackend.run()``
saves adapter files to disk but no ``LoRAAdapter`` DB row is ever created.
Now invoked from the backend-agnostic ``on_complete`` path for both local
and SaaS fine-tune results.
"""

from __future__ import annotations

import json
import logging
from typing import Any, cast

from ...db.models.lora_adapter import LoRAAdapter
from ...db.repositories.lora_adapter_repository import LoRAAdapterRepository
from ..compute.result import ComputeResult

logger = logging.getLogger(__name__)


class AdapterPersistenceService:
    """Creates a ``LoRAAdapter`` DB row from a completed ``ComputeResult``.

    Parameters
    ----------
    lora_adapter_repo : LoRAAdapterRepository
        Repository for persisting ``LoRAAdapter`` rows.
    """

    def __init__(self, lora_adapter_repo: LoRAAdapterRepository) -> None:
        self._repo = lora_adapter_repo

    async def persist(self, result: ComputeResult, config: dict[str, object]) -> None:
        """Persist a ``LoRAAdapter`` row when the result contains an adapter.

        Skips silently when ``result.adapter_id`` is ``None`` (not a
        fine-tune result).  When ``base_model_ref`` cannot be resolved to
        an ``external_model_id`` (ad-hoc/local base models), logs a warning
        and skips — the FK constraint is ``NOT NULL`` so we cannot insert
        without it.

        Parameters
        ----------
        result : ComputeResult
            Completed fine-tune result containing ``adapter_id`` and
            ``artifact_uris["adapter_path"]``.
        config : dict[str, object]
            Training config containing ``"base_model_ref"`` and LoRA
            hyperparameters (``lora_rank``, ``lora_alpha``, ``method``,
            etc.).
        """
        if result.adapter_id is None:
            return

        base_model_ref = config.get("base_model_ref")
        if base_model_ref is None:
            logger.warning(
                "Cannot persist LoRAAdapter: base_model_ref is None "
                "(adapter_id=%s, path=%s)",
                result.adapter_id,
                result.artifact_uris.get("adapter_path"),
            )
            return

        # external_model_id is a required FK — skip if ref is not numeric
        # (ad-hoc models without a registered ExternalModel).
        if not isinstance(base_model_ref, int):
            logger.warning(
                "Cannot persist LoRAAdapter: base_model_ref=%r not an int FK "
                "(adapter_id=%s). Register the base model first.",
                base_model_ref,
                result.adapter_id,
            )
            return

        adapter_path = result.artifact_uris.get("adapter_path", "")

        lora_rank_val = cast(int, config.get("lora_rank", 8))
        lora_alpha_val = cast(float, config.get("lora_alpha", 16))
        adapter = LoRAAdapter(
            external_model_id=base_model_ref,
            run_id=0,
            adapter_id=result.adapter_id or "",
            method=str(config.get("method", "lora")),
            storage_path=str(adapter_path),
            lora_rank=lora_rank_val,
            lora_alpha=lora_alpha_val,
            lora_target_modules=(
                json.dumps(config["lora_target_modules"])
                if isinstance(config.get("lora_target_modules"), list)
                else (
                    str(config["lora_target_modules"])
                    if config.get("lora_target_modules")
                    else None
                )
            ),
            lora_dropout=(
                cast(float | None, config.get("lora_dropout"))
                if config.get("lora_dropout")
                else None
            ),
            lora_bias=str(config["lora_bias"]) if config.get("lora_bias") else None,
            final_loss=result.final_loss,
        )
        await self._repo.add(adapter)
