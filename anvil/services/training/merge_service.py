"""Adapter merge service — merges LoRA adapters into base model weights.

Provides the ``AdapterMergeService`` for optionally merging a LoRA
adapter into its base model, producing a standalone model artifact
with no adapter dependency.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ...db.repositories.lora_adapter_repository import LoRAAdapterRepository
from ...storage.local import LocalFileStore

try:
    from peft import PeftModel
    from transformers import AutoModelForCausalLM

    _MERGE_DEPS_AVAILABLE = True
except ImportError:
    _MERGE_DEPS_AVAILABLE = False

logger = logging.getLogger(__name__)


class AdapterMergeService:
    """Merge a LoRA adapter into its base model to create standalone weights.

    Parameters
    ----------
    lora_adapter_repo : LoRAAdapterRepository
        Repository for adapter CRUD operations.
    store : LocalFileStore
        File store for reading adapter artifacts and writing merged output.
    """

    def __init__(
        self,
        lora_adapter_repo: LoRAAdapterRepository,
        store: LocalFileStore,
    ) -> None:
        self._repo = lora_adapter_repo
        self._store = store

    async def merge(
        self,
        model_id: int,
        adapter_id: str,
    ) -> str:
        """Merge a LoRA adapter into its base model.

        Loads the adapter, calls ``PeftModel.merge_and_unload()`` to
        produce standalone weights, saves the merged artifact, deletes
        the original adapter files, and marks the adapter as merged.

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
            If the adapter is not found or is already merged.
        """
        adapter = await self._repo.get_by_adapter_id(model_id, adapter_id)
        if adapter is None:
            raise ValueError(f"Adapter {adapter_id!r} not found for model {model_id}")
        if adapter.merged_at is not None:
            raise ValueError(
                f"Adapter {adapter_id!r} for model {model_id} is already merged"
            )

        if not _MERGE_DEPS_AVAILABLE:
            raise RuntimeError(
                "Adapter merge requires peft, torch, and transformers. "
                "Install: pip install anvil[finetune]"
            )

        merged_path = f"models/{model_id}/merged/{adapter_id}/"
        local_path = Path(adapter.storage_path) if adapter.storage_path else None

        base_model = AutoModelForCausalLM.from_pretrained(
            str(local_path.parent) if local_path else f"models/{model_id}",
            trust_remote_code=False,
        )
        adapter_model = PeftModel.from_pretrained(base_model, str(local_path))
        merged = adapter_model.merge_and_unload()

        # Save merged weights
        merged.save_pretrained(str(Path(f"data/storage/{merged_path}")))

        # Mark adapter as merged
        await self._repo.mark_merged(model_id, adapter_id)
        logger.info("Merged adapter %s/%s -> %s", model_id, adapter_id, merged_path)

        return merged_path
