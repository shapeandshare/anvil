# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Catalog entry read DTO."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .._shared.asset_state import AssetState
from .._shared.runnable_status import RunnableStatus
from .catalog_kind import CatalogKind
from .lifecycle_state import LifecycleState
from .model_ref import ModelRef


class CatalogEntry(BaseModel):
    """Read-only data transfer object for a catalog entry (a single
    model version).

    Carries every field used by listing surfaces, loaded entirely
    from MLflow tags — no per-model ``get_run`` calls (SC-008).

    Attributes
    ----------
    ref : ModelRef
        Catalog identity (name + version).
    kind : CatalogKind
        How the model entered the system.
    display_name : str
        Human-readable label (mutable, never identity).
    source_type : str
        Provider type (``"huggingface"``, ``"local"``, ``"internal"``).
    source_identifier : str
        Provider-specific identifier (e.g. HF repo ID).
    revision_sha : str or None
        Provider revision (identity triple member).
    architecture_family : str or None
        Model architecture (e.g. ``"LlamaForCausalLM"``).
    tokenizer_family : str or None
        Tokenizer type.
    license : str or None
        SPDX license identifier.
    parameter_count : int
        Number of parameters (0 if unknown).
    runnable_status : RunnableStatus
        Execution eligibility.
    runnable_reason : str or None
        Plain-text explanation if not runnable.
    asset_availability : AssetState
        Download state of model assets.
    final_loss : float or None
        Training loss (trained/merged models).
    lifecycle_state : LifecycleState
        Active or archived.
    created_at : datetime or None
        Version creation timestamp.
    config : dict or None
        Parsed config manifest.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    ref: ModelRef
    kind: CatalogKind
    display_name: str = ""
    source_type: str = ""
    source_identifier: str = ""
    revision_sha: str | None = None
    architecture_family: str | None = None
    tokenizer_family: str | None = None
    license: str | None = None
    parameter_count: int = 0
    runnable_status: RunnableStatus = RunnableStatus("track_only")
    runnable_reason: str | None = None
    asset_availability: AssetState = AssetState("metadata_only")
    final_loss: float | None = None
    lifecycle_state: LifecycleState = LifecycleState("active")
    created_at: datetime | None = None
    config: dict | None = None

    def is_playable(self) -> bool:
        """Whether this model entry supports direct inference
        generation.

        Returns
        -------
        bool
            ``True`` when the model is runnable and all assets are
            available.
        """
        return (
            self.runnable_status == RunnableStatus.RUNNABLE
            and self.asset_availability == AssetState.ASSETS_AVAILABLE
        )
