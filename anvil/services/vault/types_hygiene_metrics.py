# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""HygieneMetrics model — hygiene analysis: tag conformity, frontmatter completeness."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HygieneMetrics(BaseModel):
    """Hygiene analysis: tag conformity, frontmatter completeness, phantom links, over-linking.

    Attributes
    ----------
    non_conformant_tags : list[tuple[str, str]]
        (note, tag) pairs outside controlled vocabulary.
    near_duplicate_tags : list[tuple[str, str]]
        (tag_a, tag_b) near-duplicate pairs.
    single_use_tags : list[str]
        Tags used exactly once.
    unused_tags : list[str]
        Tags in vocabulary with zero usage.
    missing_fields : list[tuple[str, str]]
        (note, field) missing required frontmatter.
    type_mismatches : list[tuple[str, str, str]]
        (note, field, expected_type).
    inconsistent_dates : list[tuple[str, str]]
        (note, description) date inconsistencies.
    phantom_links : list[tuple[str, str]]
        (source, target) — target file doesn't exist.
    over_linking : list[tuple[str, str, str]]
        (note, section, target) excessive links.
    tag_conformity_pct : float
        Percentage conforming to vocabulary.
    tag_conformity_class : str
        Classification.
    frontmatter_completeness_pct : float
        Percentage with complete frontmatter.
    frontmatter_completeness_class : str
        Classification.
    """

    non_conformant_tags: list[tuple[str, str]] = Field(default_factory=list)
    near_duplicate_tags: list[tuple[str, str]] = Field(default_factory=list)
    single_use_tags: list[str] = Field(default_factory=list)
    unused_tags: list[str] = Field(default_factory=list)
    missing_fields: list[tuple[str, str]] = Field(default_factory=list)
    type_mismatches: list[tuple[str, str, str]] = Field(default_factory=list)
    inconsistent_dates: list[tuple[str, str]] = Field(default_factory=list)
    phantom_links: list[tuple[str, str]] = Field(default_factory=list)
    over_linking: list[tuple[str, str, str]] = Field(default_factory=list)
    tag_conformity_pct: float = 100.0
    tag_conformity_class: str = ""
    frontmatter_completeness_pct: float = 100.0
    frontmatter_completeness_class: str = ""