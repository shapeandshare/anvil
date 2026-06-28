# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""LinkPredictionResult model — output from the link prediction ensemble."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .types_scored_pair import ScoredPair


class LinkPredictionResult(BaseModel):
    """Output from the link prediction ensemble.

    Attributes
    ----------
    scored_pairs : list[ScoredPair]
        All scored candidates.
    top_n : int
        Number of top candidates to report (default 20).
    threshold : float
        Ensemble score threshold for auto-fix (default 0.7).
    took_action : bool
        Whether ``--fix`` mode inserted any links.
    """

    scored_pairs: list[ScoredPair] = Field(default_factory=list)
    top_n: int = 20
    threshold: float = 0.7
    took_action: bool = False