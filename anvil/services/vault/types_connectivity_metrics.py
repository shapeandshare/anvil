# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ConnectivityMetrics model — connectivity analysis results."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConnectivityMetrics(BaseModel):
    """Connectivity analysis results: orphans, dead ends, density, components, bidirectionals.

    Attributes
    ----------
    orphan_rate : float
        Percentage of notes with zero inbound links (0-100).
    orphan_count : int
        Count of orphan notes.
    orphans : list[str]
        Stems of orphan notes.
    dead_end_rate : float
        Percentage of notes with zero outbound links (0-100).
    dead_end_count : int
        Count of dead-end notes.
    dead_ends : list[str]
        Stems of dead-end notes.
    link_density_avg : float
        Average links per file.
    link_density_class : str
        Classification: ``healthy``, ``warning``, or ``critical``.
    largest_component_pct : float
        Size of largest WCC as percentage of total nodes.
    largest_component_class : str
        Classification.
    bidirectional_ratio : float
        Percentage of linked pairs with reciprocal links.
    bidirectional_class : str
        Classification.
    missing_reciprocals : list[tuple[str, str]]
        (source, target) pairs lacking reverse links.
    """

    orphan_rate: float = 0.0
    orphan_count: int = 0
    orphans: list[str] = Field(default_factory=list)
    dead_end_rate: float = 0.0
    dead_end_count: int = 0
    dead_ends: list[str] = Field(default_factory=list)
    link_density_avg: float = 0.0
    link_density_class: str = ""
    largest_component_pct: float = 0.0
    largest_component_class: str = ""
    bidirectional_ratio: float = 0.0
    bidirectional_class: str = ""
    missing_reciprocals: list[tuple[str, str]] = Field(default_factory=list)