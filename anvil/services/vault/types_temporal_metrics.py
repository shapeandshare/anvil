# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""TemporalMetrics model — temporal decay analysis: staleness, coherence."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TemporalMetrics(BaseModel):
    """Temporal decay analysis: staleness, coherence.

    Attributes
    ----------
    stale_notes : list[str]
        Note stems not updated in >180 days.
    dead_weight : list[str]
        Stale + orphaned notes.
    temporally_distant_pairs : list[tuple[str, str, int]]
        (a, b, delta_days) link pairs far apart in time.
    temporal_deltas : list[int]
        All link-pair time deltas.
    high_coherence_pct : float
        % of links within 90 days.
    low_coherence_pct : float
        % of links >365 days apart.
    """

    stale_notes: list[str] = Field(default_factory=list)
    dead_weight: list[str] = Field(default_factory=list)
    temporally_distant_pairs: list[tuple[str, str, int]] = Field(default_factory=list)
    temporal_deltas: list[int] = Field(default_factory=list)
    high_coherence_pct: float = 0.0
    low_coherence_pct: float = 0.0
