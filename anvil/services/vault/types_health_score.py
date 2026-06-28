# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""HealthScore model — weighted health score for the vault graph."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthScore(BaseModel):
    """Weighted health score for the vault graph (0-100).

    Attributes
    ----------
    overall : float
        Composite health score 0-100.
    orphan_score : float
        Component score 0-100.
    dead_end_score : float
        Component score 0-100.
    link_density_score : float
        Component score 0-100.
    largest_component_score : float
        Component score 0-100.
    bidirectional_score : float
        Component score 0-100.
    sink_score : float
        Component score 0-100.
    tag_conformity_score : float
        Component score 0-100.
    frontmatter_score : float
        Component score 0-100.
    breakdown : dict[str, float]
        Named breakdown for extensibility.
    """

    overall: float = 0.0
    orphan_score: float = 0.0
    dead_end_score: float = 0.0
    link_density_score: float = 0.0
    largest_component_score: float = 0.0
    bidirectional_score: float = 0.0
    sink_score: float = 0.0
    tag_conformity_score: float = 0.0
    frontmatter_score: float = 0.0
    breakdown: dict[str, float] = Field(default_factory=dict)
