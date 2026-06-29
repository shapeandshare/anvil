# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""``ResourceEnvelope`` — hardware resource requirements for a curated model."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ResourceEnvelope(BaseModel):
    """Hardware resource requirements for a curated model entry.

    Attributes
    ----------
    min_ram_gb : float
        Minimum system RAM in GB. Must be non-negative.
    min_vram_per_backend : dict[str, float]
        Per-backend minimum VRAM in GB. Must include at least a
        ``"cpu"`` key.
    supported_methods : list[str]
        Supported fine-tuning methods. Must contain at least one entry.
    """

    min_ram_gb: float = Field(ge=0, description="Minimum system RAM in GB")
    min_vram_per_backend: dict[str, float] = Field(
        description="Per-backend minimum VRAM in GB"
    )
    supported_methods: list[str] = Field(
        min_length=1, description="Supported fine-tuning methods"
    )

    @field_validator("min_vram_per_backend")
    @classmethod
    def _ensure_cpu_key(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate that the VRAM dict contains a ``"cpu"`` key.

        Parameters
        ----------
        v : dict[str, float]
            The per-backend VRAM mapping to validate.

        Returns
        -------
        dict[str, float]
            The validated mapping unchanged.

        Raises
        ------
        ValueError
            If the ``"cpu"`` key is missing from the dictionary.
        """
        if "cpu" not in v:
            msg = "min_vram_per_backend must include a 'cpu' key"
            raise ValueError(msg)
        return v


__all__ = ["ResourceEnvelope"]
