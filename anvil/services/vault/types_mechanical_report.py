# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""MechanicalReport model — output from vault mechanical audit."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .types_finding import Finding


class MechanicalReport(BaseModel):
    """Output from vault mechanical audit (frontmatter, wikilinks, links).

    Attributes
    ----------
    errors : list[Finding]
        ERROR severity findings.
    warnings : list[Finding]
        WARN severity findings.
    skipped : list[Finding]
        SKIPPED severity findings.
    stats : dict[str, int]
        Summary statistics.
    """

    errors: list[Finding] = Field(default_factory=list)
    warnings: list[Finding] = Field(default_factory=list)
    skipped: list[Finding] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)

    def add(self, finding: Finding) -> None:
        """Add a finding, routing by severity.

        Parameters
        ----------
        finding : Finding
            The finding to add.
        """
        if finding.severity == "ERROR":
            self.errors.append(finding)
        elif finding.severity == "WARN":
            self.warnings.append(finding)
        else:
            self.skipped.append(finding)
