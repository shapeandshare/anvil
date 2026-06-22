# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for GraphHealthRunner — vault scanning and graph building."""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.services.vault._types import NoteMetadata
from anvil.services.vault.scanner import GraphHealthRunner, is_exempt, should_exclude


class TestShouldExclude:
    """Tests for ``should_exclude``."""

    def test_excludes_meta(self) -> None:
        vault_root = Path("/vault")
        path = Path("/vault/_meta/tags.md")
        assert should_exclude(path, vault_root) is True

    def test_includes_normal(self) -> None:
        vault_root = Path("/vault")
        path = Path("/vault/Notes/ValidNote.md")
        assert should_exclude(path, vault_root) is False


class TestIsExempt:
    """Tests for ``is_exempt``."""

    def test_spec_subfile_is_exempt(self) -> None:
        vault_root = Path("/vault")
        path = Path("/vault/Specs/015 Demo/015 Demo - plan.md")
        meta = NoteMetadata(
            path=path,
            stem="015 Demo - plan",
            frontmatter={"title": "Plan", "type": "spec", "tags": ["type/spec"]},
            title="Plan",
            note_type="spec",
            tags=["type/spec"],
        )
        assert is_exempt(meta, vault_root) is True

    def test_scaffold_file_is_exempt(self) -> None:
        vault_root = Path("/vault")
        path = Path("/vault/Specs/015 Demo/checklists/requirements.md")
        meta = NoteMetadata(
            path=path,
            stem="requirements",
        )
        assert is_exempt(meta, vault_root) is True

    def test_normal_note_not_exempt(self) -> None:
        vault_root = Path("/vault")
        path = Path("/vault/Notes/ValidNote.md")
        meta = NoteMetadata(
            path=path,
            stem="ValidNote",
            frontmatter={
                "title": "Valid",
                "type": "decision",
                "tags": ["type/decision"],
            },
            title="Valid",
            note_type="decision",
            tags=["type/decision"],
        )
        assert is_exempt(meta, vault_root) is False

    def test_root_spec_note_not_exempt(self) -> None:
        vault_root = Path("/vault")
        path = Path("/vault/Specs/015 Demo/015 Demo.md")
        meta = NoteMetadata(
            path=path,
            stem="015 Demo",
            frontmatter={"title": "015 Demo", "type": "spec", "tags": ["type/spec"]},
            title="015 Demo",
            note_type="spec",
            tags=["type/spec"],
        )
        assert is_exempt(meta, vault_root) is False


class TestGraphHealthRunner:
    """Tests for ``GraphHealthRunner``."""

    def test_scan_all_notes(self, test_vault_dir: Path) -> None:
        runner = GraphHealthRunner(test_vault_dir, test_vault_dir)
        runner.scan_all_notes()
        assert len(runner.notes) == 5
        assert "ValidNote" in runner.notes
        assert "AnotherNote" in runner.notes

    def test_build_graph(self, test_vault_dir: Path) -> None:
        runner = GraphHealthRunner(test_vault_dir, test_vault_dir)
        runner.scan_all_notes()
        G = runner.build_graph()
        assert G is not None
        assert G.number_of_nodes() == 5
        # ValidNote links to AnotherNote
        assert G.has_edge("ValidNote", "AnotherNote")

    def test_run_all(self, test_vault_dir: Path) -> None:
        runner = GraphHealthRunner(test_vault_dir, test_vault_dir)
        runner.scan_all_notes()
        if runner.notes:
            runner.build_graph()
            report = runner.run_all()
            assert report.notes_scanned == 5
            assert report.connectivity is not None

    @pytest.mark.asyncio
    async def test_write_reports(self, test_vault_dir: Path, tmp_path: Path) -> None:
        runner = GraphHealthRunner(test_vault_dir, test_vault_dir)
        runner.scan_all_notes()
        runner.build_graph()
        report = runner.run_all()
        json_path, md_path = runner.write_reports(report, tmp_path)
        assert json_path.exists()
        assert md_path.exists()
