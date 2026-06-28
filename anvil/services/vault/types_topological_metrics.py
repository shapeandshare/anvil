# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""TopologicalMetrics model — topological analysis: PageRank, betweenness, communities."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TopologicalMetrics(BaseModel):
    """Topological analysis: PageRank, betweenness, communities, information sinks.

    Attributes
    ----------
    pagerank_top : list[tuple[str, float]]
        Top PageRank scores (note, score).
    betweenness_bridges : list[tuple[str, float]]
        High-betweenness notes (note, score).
    communities : list[list[str]]
        Louvain community clusters (stems per cluster).
    communities_needing_moc : list[list[str]]
        Communities of >=5 notes without a MOC.
    information_sinks : list[str]
        High in-degree, zero out-degree notes.
    information_sink_rate : float
        Sink count as percentage of total nodes.
    information_sink_class : str
        Classification.
    """

    pagerank_top: list[tuple[str, float]] = Field(default_factory=list)
    betweenness_bridges: list[tuple[str, float]] = Field(default_factory=list)
    communities: list[list[str]] = Field(default_factory=list)
    communities_needing_moc: list[list[str]] = Field(default_factory=list)
    information_sinks: list[str] = Field(default_factory=list)
    information_sink_rate: float = 0.0
    information_sink_class: str = ""