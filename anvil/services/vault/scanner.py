# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""GraphHealthRunner — vault wikilink graph analysis orchestrator.

Migrated from ``scripts/ci/graph_health/__init__.py``.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from ._types import GraphHealthReport, NoteMetadata

EXCLUDED_DIRS = {"_meta", ".obsidian", "addons"}
EXEMPT_TYPES: set[str] = {"type/spec"}


def should_exclude(path: Path, vault_root: Path) -> bool:
    """Check if a note path should be excluded from graph analysis.

    Parameters
    ----------
    path : Path
        Note file path to check.
    vault_root : Path
        Root directory of the vault.

    Returns
    -------
    bool
        True if the path is in an excluded directory.
    """
    try:
        rel = path.relative_to(vault_root)
    except ValueError:
        return False
    return any(part in EXCLUDED_DIRS for part in rel.parts)


def _is_scaffold_path(path: Path, vault_root: Path) -> bool:
    """Check if a path is a scaffold subdir under Specs/.

    Parameters
    ----------
    path : Path
        File path to check.
    vault_root : Path
        Root of the vault.

    Returns
    -------
    bool
        True if the path is under Specs/*/checklists/ or Specs/*/contracts/.
    """
    SCAFFOLD_SUBDIRS = {"checklists", "contracts"}
    try:
        rel = path.relative_to(vault_root)
    except ValueError:
        return False
    parts = rel.parts
    try:
        specs_idx = parts.index("Specs")
    except ValueError:
        return False
    if len(parts) < specs_idx + 4:
        return False
    return parts[specs_idx + 2] in SCAFFOLD_SUBDIRS


def _is_spec_subfile(path: Path, vault_root: Path) -> bool:
    """Check if a path is a spec subfile (not the root note).

    Parameters
    ----------
    path : Path
        File path to check.
    vault_root : Path
        Root of the vault.

    Returns
    -------
    bool
        True if the note is under Specs/NNN Title/ and its filename
        does not match ``<spec-dir>.md``, and it is not under a
        scaffold subdir.
    """
    SCAFFOLD_SUBDIRS = {"checklists", "contracts"}
    try:
        rel = path.relative_to(vault_root)
    except ValueError:
        return False
    parts = rel.parts
    try:
        specs_idx = parts.index("Specs")
    except ValueError:
        return False
    if specs_idx + 2 >= len(parts):
        return False
    # Scaffold subdir files are not spec subfiles
    if specs_idx + 3 < len(parts) and parts[specs_idx + 2] in SCAFFOLD_SUBDIRS:
        return False
    spec_dir = parts[specs_idx + 1]
    main_note = f"{spec_dir}.md"
    return parts[-1] != main_note


def is_exempt(meta: NoteMetadata, vault_root: Path) -> bool:
    """Check if a note is exempt from orphan/dead-end/sink analysis.

    Exempt notes are those under scaffold subdirs (``Specs/*/checklists/``,
    ``Specs/*/contracts/``) or spec subfiles (under ``Specs/NNN Title/``
    but not the root note). They are added to the graph so wikilinks
    resolve, but their connectivity is not counted.

    Parameters
    ----------
    meta : NoteMetadata
        Note metadata to check.
    vault_root : Path
        Root of the vault.

    Returns
    -------
    bool
        True if the note should be exempt.
    """
    if _is_scaffold_path(meta.path, vault_root):
        return True
    if _is_spec_subfile(meta.path, vault_root):
        return True
    return False


class GraphHealthRunner:
    """Entry point for graph health analysis of a vault.

    Parameters
    ----------
    vault_root : Path
        Path to the vault directory (e.g. ``docs/vault/``).
    repo_root : Path
        Path to the repository root (e.g. for ``--fix`` mode).
    """

    def __init__(self, vault_root: Path, repo_root: Path) -> None:
        self.vault_root = vault_root
        self.repo_root = repo_root
        self.notes: dict[str, NoteMetadata] = {}
        self.excluded_stems: set[str] = set()
        self.graph: Any = None
        self._filename_index: dict[str, list[Path]] | None = None

    def set_filename_index(self, index: dict[str, list[Path]]) -> None:
        """Pre-populate filename index from vault_audit.py scan.

        Parameters
        ----------
        index : dict[str, list[Path]]
            Mapping from wikilink target to list of matching file paths.
        """
        self._filename_index = index

    def scan_all_notes(self) -> None:
        """Read all vault .md files and extract metadata + wikilinks."""
        import unicodedata

        import yaml  # type: ignore[import-untyped]

        all_md = sorted(self.vault_root.rglob("*.md"))
        self.notes = {}

        for note_path in all_md:
            if should_exclude(note_path, self.vault_root):
                continue

            stem = unicodedata.normalize("NFC", note_path.stem)

            try:
                content = note_path.read_text(encoding="utf-8")
            except OSError:
                continue

            content = unicodedata.normalize("NFC", content)

            parts = content.split("---\n", 2)
            if len(parts) < 3:
                parts = content.split("---\r\n", 2)
            if len(parts) < 3:
                body = content
                fm: dict[str, Any] = {}
            else:
                fm_text = parts[1]
                body = parts[2]
                try:
                    fm = yaml.safe_load(fm_text) or {}
                except Exception:
                    fm = {}

            import re

            wikilink_pattern = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]")
            outbound_stems = [
                unicodedata.normalize("NFC", m.group(1))
                for m in wikilink_pattern.finditer(body)
            ]

            created: date | None = self._parse_date(fm.get("created"))
            updated: date | None = self._parse_date(fm.get("updated"))
            last_mod = None
            try:
                from datetime import datetime

                last_mod = datetime.fromtimestamp(note_path.stat().st_mtime)
            except OSError:
                pass

            self.notes[stem] = NoteMetadata(
                path=note_path,
                stem=stem,
                frontmatter=fm,
                title=fm.get("title"),
                note_type=fm.get("type"),
                tags=fm.get("tags", []),
                created_date=created,
                updated_date=updated,
                last_modified=last_mod,
                outbound_stems=outbound_stems,
            )

        # Identify exempt notes (scaffold files, spec subfiles) and store
        # their stems so downstream connectivity/topology can exclude them
        # from orphan/dead-end/sink counts.
        self.excluded_stems = set()
        for stem, meta in self.notes.items():
            if is_exempt(meta, self.vault_root):
                self.excluded_stems.add(stem)

    @staticmethod
    def _parse_date(val: Any) -> date | None:
        """Parse a date from frontmatter (ISO string or date object)."""
        from datetime import date

        if val is None:
            return None
        if isinstance(val, date) and not isinstance(val, datetime):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, str):
            val = val.strip().strip("'\"")
            for fmt in (
                "%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%fZ",
            ):
                try:
                    return datetime.strptime(val, fmt).date()
                except ValueError:
                    continue
        return None

    @staticmethod
    def _resolve_wikilink(target: str) -> str:
        """Strip directory prefix from a wikilink target to get the note stem."""
        if "/" in target:
            return target.rsplit("/", 1)[-1]
        return target

    def build_graph(self) -> object:
        """Build a directed wikilink graph from scanned notes.

        Returns
        -------
        nx.DiGraph
        """
        import networkx as nx

        G = nx.DiGraph()
        for stem, meta in self.notes.items():
            G.add_node(stem, file_path=str(meta.path))
            for target in meta.outbound_stems:
                resolved = self._resolve_wikilink(target)
                if resolved in self.notes:
                    G.add_edge(stem, resolved)

        for source, target in G.edges():
            if target in self.notes:
                self.notes[target].inbound_stems.append(source)

        self.graph = G
        return G

    def run_all(
        self,
        apply: bool = False,
        repo_root: Path | None = None,
    ) -> GraphHealthReport:
        """Run all health checks and return a report.

        Parameters
        ----------
        apply : bool
            If True, run ``--fix`` mode on link prediction candidates.
        repo_root : Path or None
            Repository root path (needed for ``--fix`` to find notes).

        Returns
        -------
        GraphHealthReport
        """
        from . import connectivity, hygiene
        from . import prediction as pred_mod
        from . import scoring, structural, temporal, topology

        report = GraphHealthReport()
        report.notes_scanned = len(self.notes)

        if self.graph is None or len(self.graph.nodes) == 0:
            return report

        report.connectivity = connectivity.compute_connectivity(
            self.graph,
            self.notes,
            excluded_stems=self.excluded_stems,
        )
        report.topological = topology.compute_topological(self.graph, self.notes)
        report.hygiene = hygiene.compute_hygiene(
            self.notes, self.vault_root, self._filename_index
        )
        report.temporal = temporal.compute_temporal(self.graph, self.notes)
        report.structural = structural.compute_structural(
            self.graph, self.notes, report.topological
        )

        communities = report.topological.communities
        missing = report.connectivity.missing_reciprocals
        if missing:
            result = pred_mod.compute_link_prediction(
                self.graph,
                self.notes,
                communities,
                missing,
            )
            report.link_prediction = result

        report.health_score = scoring.compute_health_score(report)
        return report

    def write_reports(
        self,
        report: GraphHealthReport,
        output_dir: Path,
    ) -> tuple[Path, Path]:
        """Write JSON + Markdown reports.

        Parameters
        ----------
        report : GraphHealthReport
            The report to write.
        output_dir : Path
            Directory to write reports into.

        Returns
        -------
        tuple[Path, Path]
            (json_path, md_path).
        """
        from . import report as report_mod

        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        json_path = output_dir / f"graph-health_{timestamp}.json"
        json_path.write_text(report.to_json(), encoding="utf-8")

        md_path = output_dir / f"graph-health_{timestamp}.md"
        md_path.write_text(
            report_mod.render_markdown(report, self.notes), encoding="utf-8"
        )

        return json_path, md_path
