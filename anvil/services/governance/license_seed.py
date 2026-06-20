"""Seed data for the approved-license catalog.

Contains the initial broad OSI/Creative-Commons set that powers
the first startup's idempotent ``GovernanceService.seed_catalog()``
call.  Maintainer-extendable — add new :class:`LicenseSeedEntry`
instances here.
"""

from __future__ import annotations

from ...db.models.license_entry import LicenseEntry


class LicenseSeedEntry:
    """Descriptor for a single entry in the seed list."""

    def __init__(
        self,
        identifier: str,
        display_name: str,
        requires_attribution: bool = False,
        redistribution_allowed: bool = True,
        is_own_content_sentinel: bool = False,
    ) -> None:
        self._identifier = identifier
        self._display_name = display_name
        self._requires_attribution = requires_attribution
        self._redistribution_allowed = redistribution_allowed
        self._is_own_content_sentinel = is_own_content_sentinel

    def to_model(self) -> LicenseEntry:
        """Build an unsaved :class:`LicenseEntry` from this descriptor."""
        return LicenseEntry(
            identifier=self._identifier,
            display_name=self._display_name,
            requires_attribution=self._requires_attribution,
            redistribution_allowed=self._redistribution_allowed,
            is_own_content_sentinel=self._is_own_content_sentinel,
        )


# ── The seed list ──────────────────────────────────────────────────────
# Broad OSI/Creative-Commons set per Clarification Q4 and research.md R6.

SEED = [
    LicenseSeedEntry("Public Domain", "Public Domain"),
    LicenseSeedEntry("CC0-1.0", "Creative Commons Zero v1.0 Universal"),
    LicenseSeedEntry("MIT", "MIT License"),
    LicenseSeedEntry("BSD-2-Clause", "BSD 2-Clause License"),
    LicenseSeedEntry("BSD-3-Clause", "BSD 3-Clause License"),
    LicenseSeedEntry("Apache-2.0", "Apache License 2.0"),
    LicenseSeedEntry(
        "CC-BY-4.0",
        "Creative Commons Attribution 4.0 International",
        requires_attribution=True,
    ),
    LicenseSeedEntry(
        "CC-BY-SA-4.0",
        "Creative Commons Attribution-ShareAlike 4.0 International",
        requires_attribution=True,
    ),
    LicenseSeedEntry("Generated/Original", "Project-generated content"),
    LicenseSeedEntry(
        "own-content",
        "Own / private / proprietary content",
        redistribution_allowed=False,
        is_own_content_sentinel=True,
    ),
]