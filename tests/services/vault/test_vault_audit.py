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
    _is_scaffold_path,
    _is_spec_subfile,
    extract_wikilinks,
    parse_frontmatter,
    validate_schema,
)


class TestIsScaffoldPath:
    """Tests for ``_is_scaffold_path``."""

    def test_scaffold_checklist_true(self) -> None:
        vault_root = Path("/vault")
        path = Path("/vault/Specs/015 Demo/checklists/requirements.md")
        assert _is_scaffold_path(path, vault_root) is True

    def test_scaffold_contracts_true(self) -> None:
        vault_root = Path("/vault")
        path = Path("/vault/Specs/015 Demo/contracts/README.md")
        assert _is_scaffold_path(path, vault_root) is True

    def test_normal_spec_file_false(self) -> None:
        vault_root = Path("/vault")
        path = Path("/vault/Specs/015 Demo/015 Demo - plan.md")
        assert _is_scaffold_path(path, vault_root) is False

    def test_root_spec_note_false(self) -> None:
        vault_root = Path("/vault")
        path = Path("/vault/Specs/015 Demo/015 Demo.md")
        assert _is_scaffold_path(path, vault_root) is False

    def test_non_spec_path_false(self) -> None:
        vault_root = Path("/vault")
        path = Path("/vault/Notes/ValidNote.md")
        assert _is_scaffold_path(path, vault_root) is False

    def test_nested_checklist_edge(self) -> None:
        vault_root = Path("/vault")
        path = Path("/vault/Specs/015 Demo/checklists/subdir/deep.md")
        assert _is_scaffold_path(path, vault_root) is True


class TestIsSpecSubfile:
    """Tests for ``_is_spec_subfile``."""

    def test_plan_subfile_true(self) -> None:
        vault_root = Path("/vault")
        path = Path("/vault/Specs/015 Demo/015 Demo - plan.md")
        assert _is_spec_subfile(path, vault_root) is True

    def test_tasks_subfile_true(self) -> None:
        vault_root = Path("/vault")
        path = Path("/vault/Specs/015 Demo/015 Demo - tasks.md")
        assert _is_spec_subfile(path, vault_root) is True

    def test_root_note_false(self) -> None:
        vault_root = Path("/vault")
        path = Path("/vault/Specs/015 Demo/015 Demo.md")
        assert _is_spec_subfile(path, vault_root) is False

    def test_non_spec_file_false(self) -> None:
        vault_root = Path("/vault")
        path = Path("/vault/Notes/ValidNote.md")
        assert _is_spec_subfile(path, vault_root) is False

    def test_checklist_file_false(self) -> None:
        vault_root = Path("/vault")
        path = Path("/vault/Specs/015 Demo/checklists/requirements.md")
        assert _is_spec_subfile(path, vault_root) is False


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

    @pytest.mark.asyncio
    async def test_spec_folder_skips_scaffold_from_schema(self, tmp_path: Path) -> None:
        """Scaffold files (checklists/, contracts/) skip schema validation.

        Scaffold files have no frontmatter and are tool-generated. They
        must be added to the filename_index (so wikilinks resolve) but
        must NOT produce schema validation errors.
        """
        spec_dir = tmp_path / "Specs" / "015 Demo"
        checklists_dir = spec_dir / "checklists"
        contracts_dir = spec_dir / "contracts"
        checklists_dir.mkdir(parents=True)
        contracts_dir.mkdir(parents=True)

        # Root spec note (has frontmatter)
        (spec_dir / "015 Demo.md").write_text(
            "---\ntitle: 015 Demo\ntype: spec\ntags:\n  - type/spec\n"
            "created: '2026-06-21'\nupdated: '2026-06-21'\n---\n# 015 Demo\n",
            encoding="utf-8",
        )
        # Spec subfile (prefixed, has frontmatter)
        (spec_dir / "015 Demo - plan.md").write_text(
            "---\ntitle: 015 Demo Plan\ntype: spec\ntags:\n  - type/spec\n"
            "created: '2026-06-21'\nupdated: '2026-06-21'\n---\n# Plan\n",
            encoding="utf-8",
        )
        # Scaffold checklist file (tool-generated, no frontmatter)
        (checklists_dir / "requirements.md").write_text(
            "# Requirements\n- [ ] Item 1\n",
            encoding="utf-8",
        )
        # Scaffold contracts file (tool-generated, no frontmatter)
        (contracts_dir / "README.md").write_text(
            "# Contract\nThis is a contract.\n",
            encoding="utf-8",
        )

        svc = VaultAuditService(vault_dir=str(tmp_path))
        report = await svc.run_mechanical_audit()

        # 4 files total: 015 Demo.md, 015 Demo - plan.md, requirements.md, README.md
        assert report.stats["files_scanned"] == 4

        # Scaffold files must produce SKIPPED findings
        skipped_rules = {f.rule for f in report.skipped}
        assert "skipped_scaffold" in skipped_rules

        # Scaffold files must NOT produce missing_frontmatter warnings
        scaffold_warnings = [
            f
            for f in report.warnings
            if "requirements" in f.note_path or "README" in f.note_path
        ]
        assert (
            scaffold_warnings == []
        ), f"Scaffold files wrongly got schema warnings: {scaffold_warnings}"

        # Wikilinks to scaffold files must resolve (they're in filename_index)
        # Root note linking to [[requirements]] must not produce broken_wikilink
        (spec_dir / "015 Demo.md").write_text(
            "---\ntitle: 015 Demo\ntype: spec\ntags:\n  - type/spec\n"
            "created: '2026-06-21'\nupdated: '2026-06-21'\n"
            "---\n# 015 Demo\nLinks to [[requirements]] and [[README]]\n",
            encoding="utf-8",
        )
        svc2 = VaultAuditService(vault_dir=str(tmp_path))
        report2 = await svc2.run_mechanical_audit()
        broken = [f for f in report2.errors if f.rule == "broken_wikilink"]
        assert not any(
            "requirements" in b.message or "README" in b.message for b in broken
        ), f"Wikilinks to scaffold files wrongly broken: {broken}"

    @pytest.mark.asyncio
    async def test_spec_subfiles_pass_schema(self, tmp_path: Path) -> None:
        """Spec subfiles (prefixed artifacts) must pass schema validation
        since they carry full frontmatter with tags: [type/spec].
        """
        spec_dir = tmp_path / "Specs" / "016 Another"
        spec_dir.mkdir(parents=True)

        (spec_dir / "016 Another.md").write_text(
            "---\ntitle: 016 Another\ntype: spec\ntags:\n  - type/spec\n"
            "created: '2026-06-21'\nupdated: '2026-06-21'\n---\n# 016 Another\n",
            encoding="utf-8",
        )
        (spec_dir / "016 Another - plan.md").write_text(
            "---\ntitle: 016 Another Plan\ntype: spec\ntags:\n  - type/spec\n"
            "created: '2026-06-21'\nupdated: '2026-06-21'\n---\n# Plan\n",
            encoding="utf-8",
        )

        svc = VaultAuditService(vault_dir=str(tmp_path))
        report = await svc.run_mechanical_audit()

        # 2 files, both with valid frontmatter -> 0 errors
        assert report.stats["files_scanned"] == 2
        # Spec subfiles have frontmatter, so no missing_frontmatter
        schema_errors = [
            f
            for f in report.errors
            if f.rule
            in ("missing_frontmatter", "missing_required_field", "missing_type_tag")
        ]
        assert (
            schema_errors == []
        ), f"Spec subfiles wrongly got schema errors: {schema_errors}"

    @pytest.mark.asyncio
    async def test_duplicate_stem_suppressed_for_spec_artifacts(
        self, tmp_path: Path
    ) -> None:
        """Duplicate filename stems across spec directories must not cause warnings.

        After prefixing, every spec has a root ``NNN Title.md`` and prefixed
        subfiles like ``NNN Title - plan.md``. Scaffold subdirs still have
        un-prefixed names (``requirements.md``, ``README.md``). The
        duplicate-stem check must suppress warnings for both cases.
        """
        spec1 = tmp_path / "Specs" / "015 Demo"
        spec2 = tmp_path / "Specs" / "020 Other"
        spec1.mkdir(parents=True)
        spec2.mkdir(parents=True)

        fm = (
            "---\ntitle: {t}\ntype: spec\ntags:\n  - type/spec\n"
            "created: '2026-06-21'\nupdated: '2026-06-21'\n---\n"
        )

        for spec, title in [(spec1, "015 Demo"), (spec2, "020 Other")]:
            (spec / f"{title}.md").write_text(
                fm.format(t=title) + f"# {title}\n", encoding="utf-8"
            )

        # Scaffold subdirs in both specs produce duplicate 'requirements' stems
        for spec in [spec1, spec2]:
            ck = spec / "checklists"
            ck.mkdir(exist_ok=True)
            (ck / "requirements.md").write_text(
                "# Requirements\n- [ ] Item\n", encoding="utf-8"
            )

        svc = VaultAuditService(vault_dir=str(tmp_path))
        report = await svc.run_mechanical_audit()

        duplicate_warnings = [
            f for f in report.warnings if f.rule == "duplicate_filename"
        ]
        # All duplicates are in scaffold subdirs -> suppressed
        assert (
            duplicate_warnings == []
        ), f"Duplicate-stem warnings not suppressed: {duplicate_warnings}"
