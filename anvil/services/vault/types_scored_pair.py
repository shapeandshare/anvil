# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ScoredPair model — a single scored missing-reciprocal candidate."""

from __future__ import annotations

from pydantic import BaseModel


class ScoredPair(BaseModel):
    """A single scored missing-reciprocal candidate.

    Attributes
    ----------
    source : str
        Source note stem.
    target : str
        Target note stem.
    ensemble_score : float
        Weighted ensemble score 0.0-1.0.
    adamic_adar : float
        Adamic-Adar structural similarity.
    tfidf_cosine : float
        TF-IDF content cosine similarity.
    community_match : float
        Community overlap score 0.0-1.0.
    """

    source: str = ""
    target: str = ""
    ensemble_score: float = 0.0
    adamic_adar: float = 0.0
    tfidf_cosine: float = 0.0
    community_match: float = 0.0
