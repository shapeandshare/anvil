"""Unit tests for anvil/services/vault/scanner.py.

Tests path exclusion helpers, exemption logic, and GraphHealthRunner
scanning/parsing behavior using temporary vault directories.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.services.vault.scanner import (
    GraphHealthRunner,
    _is_scaffold_path,
    _is_spec_subfile,
    is_exempt,
    should_exclude,
)
from anvil.services.vault.types_note_metadata import NoteMetadata

##############################################################################
# should_exclude
##############################################################################


def test_should_exclude_excluded_dir(tmp_path: Path) -> None:
    """Files under _meta/ are excluded."""
    note = tmp_path / "_meta" / "tags.md"
    note.parent.mkdir(parents=True)
    note.write_text("")
    assert should_exclude(note, tmp_path) is True


def test_should_exclude_obsidian_dir(tmp_path: Path) -> None:
    """Files under .obsidian/ are excluded."""
    note = tmp_path / ".obsidian" / "config.md"
    note.parent.mkdir(parents=True)
    note.write_text("")
    assert should_exclude(note, tmp_path) is True


def test_should_exclude_addons_dir(tmp_path: Path) -> None:
    """Files under addons/ are excluded."""
    note = tmp_path / "addons" / "plugin.py"
    note.parent.mkdir(parents=True)
    note.write_text("")
    assert should_exclude(note, tmp_path) is True


def test_should_exclude_regular_dir(tmp_path: Path) -> None:
    """Regular notes are not excluded."""
    note = tmp_path / "Specs" / "my-note.md"
    note.parent.mkdir(parents=True)
    note.write_text("")
    assert should_exclude(note, tmp_path) is False


def test_should_exclude_path_outside_vault(tmp_path: Path) -> None:
    """A path outside vault_root is not excluded."""
    outside = tmp_path / "outside" / "note.md"
    outside.parent.mkdir(parents=True)
    outside.write_text("")
    assert should_exclude(outside, tmp_path / "vault") is False


def test_should_exclude_nested_excluded(tmp_path: Path) -> None:
    """Deeply nested excluded dirs are caught."""
    note = tmp_path / "Specs" / "_meta" / "sub" / "file.md"
    note.parent.mkdir(parents=True)
    note.write_text("")
    assert should_exclude(note, tmp_path) is True


##############################################################################
# _is_scaffold_path
##############################################################################


def test_is_scaffold_checklists(tmp_path: Path) -> None:
    """Files under Specs/NNN-slug/checklists/ are scaffold."""
    note = tmp_path / "Specs" / "001-foo" / "checklists" / "checklist.md"
    note.parent.mkdir(parents=True)
    note.write_text("")
    assert _is_scaffold_path(note, tmp_path) is True


def test_is_scaffold_contracts(tmp_path: Path) -> None:
    """Files under Specs/NNN-slug/contracts/ are scaffold."""
    note = tmp_path / "Specs" / "002-bar" / "contracts" / "contract.md"
    note.parent.mkdir(parents=True)
    note.write_text("")
    assert _is_scaffold_path(note, tmp_path) is True


def test_is_scaffold_not_scaffold(tmp_path: Path) -> None:
    """Regular spec artifact is not scaffold."""
    note = tmp_path / "Specs" / "001-foo" / "spec.md"
    note.parent.mkdir(parents=True)
    note.write_text("")
    assert _is_scaffold_path(note, tmp_path) is False


def test_is_scaffold_outside_specs(tmp_path: Path) -> None:
    """Files not under Specs/ are not scaffold."""
    note = tmp_path / "Decisions" / "checklists" / "file.md"
    note.parent.mkdir(parents=True)
    note.write_text("")
    assert _is_scaffold_path(note, tmp_path) is False


def test_is_scaffold_path_outside_vault(tmp_path: Path) -> None:
    """Path outside vault_root returns False."""
    outside = tmp_path / "outside" / "Specs" / "foo" / "checklists" / "c.md"
    outside.parent.mkdir(parents=True)
    outside.write_text("")
    assert _is_scaffold_path(outside, tmp_path / "vault") is False


##############################################################################
# _is_spec_subfile
##############################################################################


def test_is_spec_subfile_true(tmp_path: Path) -> None:
    """A file under Specs/NNN Title/ that is not the root note."""
    spec_dir = tmp_path / "Specs" / "001 Foo Bar"
    spec_dir.mkdir(parents=True)
    note = spec_dir / "tasks.md"
    note.write_text("")
    assert _is_spec_subfile(note, tmp_path) is True


def test_is_spec_subfile_root_note(tmp_path: Path) -> None:
    """The root note matching its directory name is NOT a subfile."""
    spec_dir = tmp_path / "Specs" / "001 Foo Bar"
    spec_dir.mkdir(parents=True)
    note = spec_dir / "001 Foo Bar.md"
    note.write_text("")
    assert _is_spec_subfile(note, tmp_path) is False


def test_is_spec_subfile_scaffold_not_subfile(tmp_path: Path) -> None:
    """Files in scaffold dirs are NOT spec subfiles."""
    note = tmp_path / "Specs" / "001-foo" / "checklists" / "tasks.md"
    note.parent.mkdir(parents=True)
    note.write_text("")
    assert _is_spec_subfile(note, tmp_path) is False


def test_is_spec_subfile_outside_specs(tmp_path: Path) -> None:
    """Files not under Specs/ are not subfiles."""
    note = tmp_path / "Decisions" / "bar.md"
    note.parent.mkdir(parents=True)
    note.write_text("")
    assert _is_spec_subfile(note, tmp_path) is False


def test_is_spec_subfile_shallow(tmp_path: Path) -> None:
    """File at Specs/ level (not deep enough) returns False."""
    note = tmp_path / "Specs" / "tasks.md"
    note.parent.mkdir(parents=True)
    note.write_text("")
    assert _is_spec_subfile(note, tmp_path) is False


##############################################################################
# is_exempt
##############################################################################


def test_is_exempt_scaffold(tmp_path: Path) -> None:
    """Scaffold files are exempt from orphan/dead-end analysis."""
    note_path = tmp_path / "Specs" / "001-foo" / "checklists" / "c.md"
    note_path.parent.mkdir(parents=True)
    note_path.write_text("")
    meta = NoteMetadata(path=note_path, stem="c")
    assert is_exempt(meta, tmp_path) is True


def test_is_exempt_spec_subfile(tmp_path: Path) -> None:
    """Spec subfiles are exempt."""
    spec_dir = tmp_path / "Specs" / "001 Foo Bar"
    spec_dir.mkdir(parents=True)
    note_path = spec_dir / "tasks.md"
    note_path.write_text("")
    meta = NoteMetadata(path=note_path, stem="tasks")
    assert is_exempt(meta, tmp_path) is True


def test_is_exempt_not_exempt(tmp_path: Path) -> None:
    """Regular notes are NOT exempt."""
    note_path = tmp_path / "note.md"
    note_path.write_text("")
    meta = NoteMetadata(path=note_path, stem="note")
    assert is_exempt(meta, tmp_path) is False


##############################################################################
# GraphHealthRunner.scan_all_notes
##############################################################################


def test_scan_all_notes_basic(tmp_path: Path) -> None:
    """scan_all_notes finds and parses .md files in the vault."""
    note = tmp_path / "hello.md"
    note.write_text(
        "---\ntitle: Hello\ntype: note\ntags:\n  - foo\ncreated: 2024-01-15\n---\n"
        "Hello [[world]] and [[foo|display]]."
    )
    runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
    runner.scan_all_notes()

    assert "hello" in runner.notes
    meta = runner.notes["hello"]
    assert meta.title == "Hello"
    assert meta.note_type == "note"
    assert meta.tags == ["foo"]
    assert meta.outbound_stems == ["world", "foo"]


def test_scan_all_notes_excludes_excluded_dirs(tmp_path: Path) -> None:
    """Notes in excluded dirs are skipped."""
    excluded = tmp_path / "_meta" / "tags.md"
    excluded.parent.mkdir(parents=True)
    excluded.write_text("# Tags")

    note = tmp_path / "real.md"
    note.write_text("Real content.")
    runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
    runner.scan_all_notes()

    assert "_meta" not in runner.notes
    assert "real" in runner.notes
    assert "tags" not in runner.notes


def test_scan_all_notes_excludes_scaffold(tmp_path: Path) -> None:
    """Scaffold files are skipped (not added to notes dict)."""
    scaffold = tmp_path / "Specs" / "001-foo" / "checklists" / "checklist.md"
    scaffold.parent.mkdir(parents=True)
    scaffold.write_text("Checklist content")

    runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
    runner.scan_all_notes()

    # Scaffold files are skipped in scan_all_notes (so they don't
    # overwrite real notes with duplicate stems)
    assert "checklist" not in runner.notes


def test_scan_all_notes_no_frontmatter(tmp_path: Path) -> None:
    """Files without frontmatter are parsed with empty frontmatter."""
    note = tmp_path / "bare.md"
    note.write_text("Just body text with [[wikilink]].")
    runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
    runner.scan_all_notes()

    assert "bare" in runner.notes
    meta = runner.notes["bare"]
    assert meta.frontmatter == {}
    assert meta.outbound_stems == ["wikilink"]


def test_scan_all_notes_unreadable_file(tmp_path: Path) -> None:
    """Unreadable files are silently skipped (no crash)."""
    note = tmp_path / "broken.md"
    note.write_text("content")
    note.chmod(0o000)
    try:
        runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
        runner.scan_all_notes()
        assert "broken" not in runner.notes
    finally:
        note.chmod(0o644)


def test_scan_all_notes_related_frontmatter(tmp_path: Path) -> None:
    """Wikilinks inside related: frontmatter are extracted."""
    note = tmp_path / "main.md"
    note.write_text(
        "---\nrelated:\n  - '[[other]]'\n  - '[[another|label]]'\n---\nBody."
    )
    runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
    runner.scan_all_notes()

    meta = runner.notes["main"]
    assert "other" in meta.outbound_stems
    assert "another" in meta.outbound_stems


def test_scan_all_notes_deduplicates_wikilinks(tmp_path: Path) -> None:
    """Duplicate wikilink targets are deduplicated preserving order."""
    note = tmp_path / "main.md"
    note.write_text("[[dup]] text [[dup]] more [[unique]]")
    runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
    runner.scan_all_notes()

    meta = runner.notes["main"]
    assert meta.outbound_stems == ["dup", "unique"]


def test_scan_all_notes_empty_vault(tmp_path: Path) -> None:
    """An empty vault yields no notes."""
    runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
    runner.scan_all_notes()
    assert runner.notes == {}


def test_scan_all_notes_malformed_yaml(tmp_path: Path) -> None:
    """Malformed YAML frontmatter defaults to empty dict (graceful)."""
    note = tmp_path / "broken.md"
    note.write_text("---\ntitle: unclosed\n: bad yaml\n---\nBody [[link]].")
    runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
    runner.scan_all_notes()

    assert "broken" in runner.notes
    meta = runner.notes["broken"]
    # If yaml is not available, frontmatter is {}
    # If yaml is available, malformed content will cause empty fm too
    assert meta.outbound_stems == ["link"]


def test_scan_all_notes_dates_parsed(tmp_path: Path) -> None:
    """ISO date strings in frontmatter are parsed correctly."""
    note = tmp_path / "dated.md"
    note.write_text(
        "---\ncreated: 2024-06-15\nupdated: 2024-06-20T14:30:00\n---\nBody."
    )
    runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
    runner.scan_all_notes()

    meta = runner.notes["dated"]
    assert meta.created_date is not None
    assert meta.created_date.isoformat() == "2024-06-15"
    assert meta.updated_date is not None
    assert meta.updated_date.isoformat() == "2024-06-20"


def test_scan_all_notes_date_with_z_suffix(tmp_path: Path) -> None:
    """ISO dates with Z suffix are parsed."""
    note = tmp_path / "znote.md"
    note.write_text("---\ncreated: 2024-01-01T00:00:00.000Z\n---\nBody.")
    runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
    runner.scan_all_notes()
    meta = runner.notes["znote"]
    assert meta.created_date is not None
    assert meta.created_date.isoformat() == "2024-01-01"


def test_scan_all_notes_identifies_exempt_stems(tmp_path: Path) -> None:
    """Exempt (spec-subfile) notes are tracked in excluded_stems."""
    spec_dir = tmp_path / "Specs" / "001 Foo"
    spec_dir.mkdir(parents=True)
    root = spec_dir / "001 Foo.md"
    root.write_text("Root note.")
    sub = spec_dir / "plan.md"
    sub.write_text("Plan note [[something]].")

    regular = tmp_path / "regular.md"
    regular.write_text("Regular.")

    runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
    runner.scan_all_notes()

    # The spec subfile "plan" is in excluded_stems
    # The root note "001 Foo" is NOT a subfile (matches dir name)
    # "regular" is not exempt
    assert "plan" in runner.excluded_stems
    assert "001 Foo" not in runner.excluded_stems
    assert "regular" not in runner.excluded_stems


##############################################################################
# _parse_date
##############################################################################


def test_parse_date_none() -> None:
    """None input returns None."""
    assert GraphHealthRunner._parse_date(None) is None


def test_parse_date_date_obj() -> None:
    """A date object passes through."""
    from datetime import date

    d = date(2024, 6, 15)
    assert GraphHealthRunner._parse_date(d) == d


def test_parse_date_datetime_obj() -> None:
    """A datetime object converts to date."""
    from datetime import datetime

    dt = datetime(2024, 6, 15, 10, 30, 0)
    result = GraphHealthRunner._parse_date(dt)
    assert result is not None
    assert result.isoformat() == "2024-06-15"


def test_parse_date_iso_string() -> None:
    """An ISO date string is parsed."""
    result = GraphHealthRunner._parse_date("2024-06-15")
    assert result is not None
    assert result.isoformat() == "2024-06-15"


def test_parse_date_datetime_string() -> None:
    """A datetime string is parsed to date."""
    result = GraphHealthRunner._parse_date("2024-06-15T14:30:00")
    assert result is not None
    assert result.isoformat() == "2024-06-15"


def test_parse_date_invalid_string() -> None:
    """An unparseable string returns None."""
    assert GraphHealthRunner._parse_date("not-a-date") is None


def test_parse_date_invalid_type() -> None:
    """An int returns None."""
    assert GraphHealthRunner._parse_date(12345) is None


def test_parse_date_quoted_iso_string(tmp_path: Path) -> None:
    """A date string wrapped in single quotes is parsed."""
    result = GraphHealthRunner._parse_date("'2024-06-15'")
    assert result is not None
    assert result.isoformat() == "2024-06-15"


##############################################################################
# _resolve_wikilink
##############################################################################


def test_resolve_wikilink_simple() -> None:
    """A simple target returns as-is."""
    assert GraphHealthRunner._resolve_wikilink("hello") == "hello"


def test_resolve_wikilink_with_dir() -> None:
    """A path-style target is stripped to the last segment."""
    assert GraphHealthRunner._resolve_wikilink("foo/bar/baz") == "baz"


def test_resolve_wikilink_single_dir() -> None:
    """A single-level path is stripped."""
    assert GraphHealthRunner._resolve_wikilink("dir/note") == "note"


##############################################################################
# GraphHealthRunner.build_graph
##############################################################################


def test_build_graph_basic(tmp_path: Path) -> None:
    """build_graph creates nodes and edges from notes."""
    a = tmp_path / "a.md"
    a.write_text("[[b]]")
    b = tmp_path / "b.md"
    b.write_text("[[c]]")
    c = tmp_path / "c.md"
    c.write_text("No links.")

    runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
    runner.scan_all_notes()

    # Need networkx for build_graph
    runner.build_graph()

    assert runner.graph is not None
    assert runner.graph.has_edge("a", "b")
    assert runner.graph.has_edge("b", "c")
    assert not runner.graph.has_edge("a", "c")


def test_build_graph_populates_inbound(tmp_path: Path) -> None:
    """build_graph sets inbound_stems on notes."""
    a = tmp_path / "a.md"
    a.write_text("[[b]]")
    b = tmp_path / "b.md"
    b.write_text("[[a]]")

    runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
    runner.scan_all_notes()
    runner.build_graph()

    assert "a" in runner.notes["b"].inbound_stems
    assert "b" in runner.notes["a"].inbound_stems


def test_build_graph_ignores_missing_targets(tmp_path: Path) -> None:
    """Wikilinks to non-existent notes are not added as edges."""
    a = tmp_path / "a.md"
    a.write_text("[[missing]]")
    b = tmp_path / "b.md"
    b.write_text("Content.")

    runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
    runner.scan_all_notes()
    runner.build_graph()

    assert runner.graph is not None
    assert "missing" not in runner.graph.nodes


def test_build_graph_empty_vault(tmp_path: Path) -> None:
    """An empty vault builds an empty graph."""
    runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
    runner.scan_all_notes()
    runner.build_graph()
    assert runner.graph is not None
    assert len(runner.graph.nodes) == 0


##############################################################################
# GraphHealthRunner.run_all
##############################################################################


def test_run_all_empty_vault(tmp_path: Path) -> None:
    """run_all with no notes returns a report with notes_scanned=0."""
    runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
    runner.scan_all_notes()
    report = runner.run_all()
    assert report.notes_scanned == 0
    # Other fields should be default empties
    assert report.connectivity.orphan_rate == 0.0


def test_run_all_with_notes(tmp_path: Path) -> None:
    """run_all produces a fully populated report for a non-empty vault."""
    a = tmp_path / "a.md"
    a.write_text("---\ntitle: A\ntype: note\ntags:\n  - foo\n---\n[[b]]")
    b = tmp_path / "b.md"
    b.write_text("---\ntitle: B\ntype: note\ntags:\n  - foo\n---\n[[a]]")

    runner = GraphHealthRunner(vault_root=tmp_path, repo_root=tmp_path)
    runner.scan_all_notes()
    report = runner.run_all()

    assert report.notes_scanned == 2
    assert report.connectivity is not None
    assert report.topological is not None
    assert report.hygiene is not None
    assert report.temporal is not None
    assert report.structural is not None
    assert report.health_score is not None
