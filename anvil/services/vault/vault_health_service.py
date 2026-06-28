# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""VaultHealthService — orchestrator wrapping audit and graph health services.

Provides a unified entry point for running vault audits with optional
graph health analysis, and convenience methods for individual checks.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from ._types import GraphHealthReport, MechanicalReport
from .scanner import GraphHealthRunner
from .vault_audit import VaultAuditService


class VaultHealthService:
    """Orchestrator for vault health analysis.

    Wraps :class:`VaultAuditService` and :class:`GraphHealthRunner`
    with a unified interface.

    Parameters
    ----------
    vault_dir : str
        Path to the Obsidian vault directory.
    """

    def __init__(self, vault_dir: str = "docs/vault") -> None:
        self.vault_dir = Path(vault_dir)
        self.audit_svc = VaultAuditService(vault_dir=vault_dir)

    async def run_full_audit(
        self,
        skip_graph_health: bool = False,
    ) -> tuple[MechanicalReport, GraphHealthReport | None]:
        """Run full vault audit (mechanical + optional graph health).

        Parameters
        ----------
        skip_graph_health : bool
            If True, skip networkx graph health analysis.

        Returns
        -------
        tuple[MechanicalReport, GraphHealthReport | None]
            (mechanical_report, graph_health_report_or_None).
        """
        mech = await self.audit_svc.run_mechanical_audit()

        gh: GraphHealthReport | None = None
        if not skip_graph_health:
            try:
                runner = GraphHealthRunner(self.vault_dir, self.vault_dir)
                runner.set_filename_index(self.audit_svc.build_filename_index())
                runner.scan_all_notes()
                if runner.notes:
                    runner.build_graph()
                    gh = runner.run_all()
            except ImportError:
                pass

        return mech, gh


class GraphHealthService:
    """Convenience wrapper for vault graph health analysis.

    Parameters
    ----------
    vault_dir : str
        Path to the vault directory.
    """

    def __init__(self, vault_dir: str) -> None:
        self.vault_dir = Path(vault_dir)

    async def analyze(self) -> GraphHealthReport:
        """Run graph health analysis.

        Returns
        -------
        GraphHealthReport
        """
        return await asyncio.to_thread(self._analyze_sync)

    def _analyze_sync(self) -> GraphHealthReport:
        """Run graph health analysis synchronously.

        Returns
        -------
        GraphHealthReport
        """
        runner = GraphHealthRunner(self.vault_dir, self.vault_dir)
        runner.scan_all_notes()
        if runner.notes:
            runner.build_graph()
            return runner.run_all()
        return GraphHealthReport()
