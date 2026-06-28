# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""GraphHealthReport model — aggregate output from all analysis passes."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from .types_connectivity_metrics import ConnectivityMetrics
from .types_health_score import HealthScore
from .types_hygiene_metrics import HygieneMetrics
from .types_link_prediction_result import LinkPredictionResult
from .types_structural_metrics import StructuralMetrics
from .types_temporal_metrics import TemporalMetrics
from .types_topological_metrics import TopologicalMetrics


def _convert_types(obj: object) -> object:
    """Convert non-serializable types for JSON serialization.

    Parameters
    ----------
    obj : object
        Object to convert.

    Returns
    -------
    object
        JSON-serializable representation.
    """
    if isinstance(obj, (Path, date, datetime)):
        return str(obj)
    if isinstance(obj, set):
        return sorted(obj)
    return obj


class GraphHealthReport(BaseModel):
    """Aggregate output from all analysis passes.

    Attributes
    ----------
    connectivity : ConnectivityMetrics
        Connectivity analysis.
    topological : TopologicalMetrics
        Topological analysis.
    hygiene : HygieneMetrics
        Hygiene analysis.
    temporal : TemporalMetrics
        Temporal decay analysis.
    structural : StructuralMetrics
        Structural gap analysis.
    health_score : HealthScore
        Composite health score.
    link_prediction : LinkPredictionResult
        Link prediction results.
    excluded_notes : list[str]
        Notes excluded from analysis.
    notes_scanned : int
        Total notes scanned.
    notes_excluded : int
        Notes excluded count.
    """

    connectivity: ConnectivityMetrics = Field(default_factory=ConnectivityMetrics)
    topological: TopologicalMetrics = Field(default_factory=TopologicalMetrics)
    hygiene: HygieneMetrics = Field(default_factory=HygieneMetrics)
    temporal: TemporalMetrics = Field(default_factory=TemporalMetrics)
    structural: StructuralMetrics = Field(default_factory=StructuralMetrics)
    health_score: HealthScore = Field(default_factory=HealthScore)
    link_prediction: LinkPredictionResult = Field(default_factory=LinkPredictionResult)
    excluded_notes: list[str] = Field(default_factory=list)
    notes_scanned: int = 0
    notes_excluded: int = 0

    def to_json(self) -> str:
        """Serialize to JSON, converting non-serializable types.

        Returns
        -------
        str
            JSON string.
        """
        raw = self.model_dump()
        return json.dumps(raw, indent=2, default=_convert_types)
