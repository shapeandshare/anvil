# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for VaultAuditService — mechanical audit."""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.services.vault.vault_audit import (
    VaultAuditService,
    extract_wikilinks,
    parse_frontmatter,
    validate_schema,
)


class TestParseFrontmatter:
    """Tests for ``parse_frontmatter``."""

    def test_valid_frontmatter(self, test_vault_dir: Path) -> None:
        path = test_vault_dir / "ValidNote.md"
        fm = parse_frontmatter(path)
        assert fm.get("title") == "Valid Test Note"
        assert "type/decision" in fm.get("tags", [])

    def test_missing_frontmatter(self) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("# No Frontmatter\n")
            tmp = Path(f.name)
        try:
            fm = parse_frontmatter(tmp)
            assert fm == {}
        finally:
            tmp.unlink()


class TestExtractWikilinks:
    """Tests for ``extract_wikilinks``."""

    def test_basic_wikilinks(self) -> None:
        text = "See [[TargetNote]] and [[OtherNote|display]]."
        links = extract_wikilinks(text)
        assert "TargetNote" in links
        assert "OtherNote" in links

    def test_skips_attachments(self) -> None:
        text = "![[image.png]] and [[ValidLink]]."
        links = extract_wikilinks(text)
        assert "ValidLink" in links
        assert "image.png" not in links

    def test_skips_code_blocks(self) -> None:
        text = "```\n[[IgnoredLink]]\n```\n[[RealLink]]"
        links = extract_wikilinks(text)
        assert "RealLink" in links
        assert "IgnoredLink" not in links


class TestValidateSchema:
    """Tests for ``validate_schema``."""

    def test_valid_note(self, test_vault_dir: Path) -> None:
        path = test_vault_dir / "ValidNote.md"
        fm = parse_frontmatter(path)
        findings = validate_schema(path, fm, "ValidNote.md")
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def test_invalid_note(self, test_vault_dir: Path) -> None:
        path = test_vault_dir / "InvalidNote.md"
        fm = parse_frontmatter(path)
        findings = validate_schema(path, fm, "InvalidNote.md")
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) > 0
        rules = {f.rule for f in errors}
        assert "missing_required_field" in rules
        assert "invalid_date" in rules


class TestVaultAuditService:
    """Tests for ``VaultAuditService``."""

    @pytest.mark.asyncio
    async def test_run_mechanical_audit(self, test_vault_dir: Path) -> None:
        svc = VaultAuditService(vault_dir=str(test_vault_dir))
        report = await svc.run_mechanical_audit()
        assert report.stats["files_scanned"] == 5
        assert len(report.errors) > 0  # invalid note + broken wikilinks
        assert len(report.warnings) >= 0

    def test_build_filename_index(self, test_vault_dir: Path) -> None:
        svc = VaultAuditService(vault_dir=str(test_vault_dir))
        index = svc.build_filename_index()
        assert "ValidNote" in index
        assert "InvalidNote" in index
        assert "AnotherNote" in index

    @pytest.mark.asyncio
    async def test_forward_wikilink_not_flagged_broken(
        self, test_vault_dir: Path
    ) -> None:
        """A wikilink to an existing file that sorts later is not broken.

        Regression test: the filename index must be built fully before
        wikilink resolution, so links to alphabetically-later targets
        (e.g. ``AnotherNote`` -> ``[[OrphanNote]]``) resolve correctly.
        """
        svc = VaultAuditService(vault_dir=str(test_vault_dir))
        report = await svc.run_mechanical_audit()
        broken_targets = {
            f.message for f in report.errors if f.rule == "broken_wikilink"
        }
        # OrphanNote.md exists and sorts after AnotherNote.md; it must
        # not be reported as a broken target.
        assert not any(
            "OrphanNote" in m for m in broken_targets
        ), f"Existing forward-link target wrongly flagged: {broken_targets}"

    @pytest.mark.asyncio
    async def test_forward_wikilink_resolves(self, tmp_path: Path) -> None:
        """A link to an alphabetically-later note must not be reported broken.

        Regression: the filename index was previously populated incrementally
        inside the audit loop, so a note linking to a target that sorted after
        it (e.g. ``Aaa`` -> ``Zzz``) was flagged as a broken wikilink because
        the target had not yet been indexed.
        """
        fm = (
            "---\n"
            "title: {title}\n"
            "type: reference\n"
            "tags:\n  - type/reference\n"
            "created: '2026-06-19'\n"
            "updated: '2026-06-19'\n"
            "aliases:\n  - {title}\n"
            "---\n"
        )
        (tmp_path / "Aaa.md").write_text(
            fm.format(title="Aaa") + "Links forward to [[Zzz]].\n",
            encoding="utf-8",
        )
        (tmp_path / "Zzz.md").write_text(
            fm.format(title="Zzz") + "A leaf note.\n",
            encoding="utf-8",
        )

        svc = VaultAuditService(vault_dir=str(tmp_path))
        report = await svc.run_mechanical_audit()

        broken = [f for f in report.errors if f.rule == "broken_wikilink"]
        assert broken == [], f"unexpected broken wikilinks: {broken}"
