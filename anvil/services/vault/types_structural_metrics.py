# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""StructuralMetrics model — structural gap analysis: chain gaps, silos, broken cycles."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StructuralMetrics(BaseModel):
    """Structural gap analysis: chain gaps, silos, broken cycles.

    Attributes
    ----------
    chain_gaps : list[tuple[str, str, str]]
        (a, c, b_intermediate) — missing intermediate concepts.
    potential_silos : list[tuple[int, int, float]]
        (cluster_a, cluster_b, density) isolated clusters.
    broken_cycles : list[list[str]]
        Cycles with no external connections.
    """

    chain_gaps: list[tuple[str, str, str]] = Field(default_factory=list)
    potential_silos: list[tuple[int, int, float]] = Field(default_factory=list)
    broken_cycles: list[list[str]] = Field(default_factory=list)
