# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for migrate_specs — spec-to-vault migration logic."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from anvil.services.vault.migrate_specs import (
    ARTIFACT_TYPES,
    _migrate_artifact_file,
    _move_scaffold_dir,
    _write_root_index_note,
    apply_migration,
    assign_domain,
    build_migration_plan,
    dry_run_migration,
    parse_created_date,
    slug_to_title,
    spec_dirname_to_title,
    verify_migration,
)


class TestSlugToTitle:
    """Tests for ``slug_to_title`` — kebab-case to Title Case."""

    def test_basic_conversion(self) -> None:
        """Basic kebab-case words get .title() treatment."""
        assert slug_to_title("bootstrap-llm-workbench") == "Bootstrap LLM Workbench"

    def test_acronym_override(self) -> None:
        """Known acronyms use their mapped casing."""
        assert slug_to_title("saas-architecture") == "SaaS Architecture"
        assert slug_to_title("owasp-remediation") == "OWASP Remediation"
        assert (
            slug_to_title("mlflow-experiment-tracking") == "MLflow Experiment Tracking"
        )
        assert slug_to_title("cli-tool") == "CLI Tool"
        assert slug_to_title("ux-rules") == "UX Rules"
        assert slug_to_title("e2e-testing") == "E2E Testing"

    def test_single_word(self) -> None:
        """Single word slug."""
        assert slug_to_title("engine") == "Engine"

    def test_all_acronyms(self) -> None:
        """Slug made entirely of acronyms."""
        assert slug_to_title("api-ux-dx") == "API UX DX"

    def test_mixed_acronym_and_regular(self) -> None:
        """Mix of acronym and regular words."""
        assert (
            slug_to_title("unified-interface-local-tls")
            == "Unified Interface Local TLS"
        )


class TestSpecDirnameToTitle:
    """Tests for ``spec_dirname_to_title`` — full dirname to title."""

    def test_full_conversion(self) -> None:
        """Full spec dirname converts correctly."""
        result = spec_dirname_to_title("001-bootstrap-llm-workbench")
        assert result == "001 Bootstrap LLM Workbench"

    def test_with_acronym(self) -> None:
        """Dirname with acronym converts with correct casing."""
        result = spec_dirname_to_title("016-saas-architecture")
        assert result == "016 SaaS Architecture"

    def test_leading_zero_preserved(self) -> None:
        """Leading zeros in spec number are preserved."""
        result = spec_dirname_to_title("023-header-api-versioning")
        assert result == "023 Header API Versioning"


class TestAssignDomain:
    """Tests for ``assign_domain`` — domain tag assignment."""

    def test_core_domain(self) -> None:
        """'engine' in slug assigns domain/core."""
        assert assign_domain("llama-engine-evolution") == "domain/core"

    def test_training_domain(self) -> None:
        """'dataset' in slug assigns domain/training."""
        assert assign_domain("dataset-curation") == "domain/training"

    def test_ui_domain(self) -> None:
        """'ui' in slug assigns domain/ui."""
        assert assign_domain("ux-rules-integration") == "domain/ui"

    def test_infrastructure_domain(self) -> None:
        """'saas' in slug assigns domain/infrastructure."""
        assert assign_domain("saas-architecture") == "domain/infrastructure"

    def test_tracking_domain(self) -> None:
        """'tracking' in slug assigns domain/tracking."""
        assert assign_domain("mlflow-experiment-tracking") == "domain/tracking"

    def test_tooling_domain(self) -> None:
        """'release' in slug assigns domain/tooling."""
        assert assign_domain("automated-semver-release") == "domain/tooling"

    def test_governance_domain(self) -> None:
        """'governance' in slug assigns domain/governance."""
        assert assign_domain("responsible-data-governance") == "domain/governance"

    def test_default_domain(self) -> None:
        """Unknown keywords get domain/vault."""
        assert assign_domain("mystery-module") == "domain/vault"


class TestParseCreatedDate:
    """Tests for ``parse_created_date`` — extract date from spec.md."""

    def test_finds_date(self) -> None:
        """**Created**: YYYY-MM-DD line is found."""
        content = "# Title\n\n**Created**: 2026-06-21\n\n## Section\n"
        assert parse_created_date(content) == "2026-06-21"

    def test_no_date(self) -> None:
        """No **Created** line returns empty string."""
        content = "# Title\n\nNo date here\n"
        assert parse_created_date(content) == ""

    def test_date_with_extra_whitespace(self) -> None:
        """Whitespace around date is handled."""
        content = "**Created**:   2026-06-21  \n"
        assert parse_created_date(content) == "2026-06-21"


class TestMigrationPlan:
    """Tests for ``build_migration_plan`` — plan generation."""

    def test_plan_has_correct_number_of_entries(
        self, temp_specs_env: tuple[Path, Path]
    ) -> None:
        """Plan has one entry per spec dir."""
        specs_dir, vault_specs_dir = temp_specs_env
        plan = build_migration_plan(specs_dir, vault_specs_dir)
        assert len(plan) == 2  # two test spec dirs

    def test_plan_entry_structure(self, temp_specs_env: tuple[Path, Path]) -> None:
        """Each plan entry has all required fields."""
        specs_dir, vault_specs_dir = temp_specs_env
        plan = build_migration_plan(specs_dir, vault_specs_dir)
        entry = plan[0]
        assert "source" in entry
        assert "target_dir" in entry
        assert "title" in entry
        assert "number" in entry
        assert "slug" in entry
        assert "artifacts" in entry
        assert "scaffold_dirs" in entry
        assert "root_note_path" in entry
        assert entry["title"] == "001 Bootstrap LLM Workbench"

    def test_plan_includes_artifacts(self, temp_specs_env: tuple[Path, Path]) -> None:
        """Plan entry includes all artifact files."""
        specs_dir, vault_specs_dir = temp_specs_env
        plan = build_migration_plan(specs_dir, vault_specs_dir)
        # Spec 001 has all artifacts
        entry001 = next(e for e in plan if e["number"] == "001")
        artifact_fnames = {a["filename"] for a in entry001["artifacts"]}
        assert "001 Bootstrap LLM Workbench - spec.md" in artifact_fnames
        assert "001 Bootstrap LLM Workbench - plan.md" in artifact_fnames
        assert "001 Bootstrap LLM Workbench - tasks.md" in artifact_fnames
        assert "001 Bootstrap LLM Workbench - data-model.md" in artifact_fnames

    def test_plan_includes_scaffold_dirs(
        self, temp_specs_env: tuple[Path, Path]
    ) -> None:
        """Plan entry includes scaffold subdirectories."""
        specs_dir, vault_specs_dir = temp_specs_env
        plan = build_migration_plan(specs_dir, vault_specs_dir)
        entry001 = next(e for e in plan if e["number"] == "001")
        target_dirs = {s["target"] for s in entry001["scaffold_dirs"]}
        assert any("checklists" in t for t in target_dirs)
        assert any("contracts" in t for t in target_dirs)

    def test_plan_handles_spec_only(self, temp_specs_env: tuple[Path, Path]) -> None:
        """Spec 023 (spec-only) has no extra artifacts or scaffold dirs."""
        specs_dir, vault_specs_dir = temp_specs_env
        plan = build_migration_plan(specs_dir, vault_specs_dir)
        entry023 = next(e for e in plan if e["number"] == "023")
        assert len(entry023["artifacts"]) == 1  # only spec.md
        assert len(entry023["scaffold_dirs"]) == 0

    def test_plan_empty_with_no_specs_dir(self, tmp_path: Path) -> None:
        """Plan is empty when specs dir doesn't exist."""
        specs_dir = tmp_path / "nonexistent"
        vault_specs_dir = tmp_path / "vault" / "Specs"
        plan = build_migration_plan(specs_dir, vault_specs_dir)
        assert plan == []

    def test_plan_artifact_has_correct_type(
        self, temp_specs_env: tuple[Path, Path]
    ) -> None:
        """Each artifact file gets the correct type from ARTIFACT_TYPES."""
        specs_dir, vault_specs_dir = temp_specs_env
        plan = build_migration_plan(specs_dir, vault_specs_dir)
        entry001 = next(e for e in plan if e["number"] == "001")
        for art in entry001["artifacts"]:
            original_stem = art["filename"].split(" - ", 1)[1]
            expected_type = ARTIFACT_TYPES.get(original_stem, "unknown")
            assert (
                art["type"] == expected_type
            ), f"Expected type {expected_type} for {original_stem}, got {art['type']}"

    def test_spec_md_content_is_loaded(self, temp_specs_env: tuple[Path, Path]) -> None:
        """Plan entry includes spec.md content when present."""
        specs_dir, vault_specs_dir = temp_specs_env
        plan = build_migration_plan(specs_dir, vault_specs_dir)
        entry001 = next(e for e in plan if e["number"] == "001")
        assert "Feature Specification" in entry001["spec_md_content"]
        assert "2026-06-20" in entry001["spec_md_content"]


class TestDryRun:
    """Tests for ``dry_run_migration``."""

    def test_dry_run_returns_lines(self, temp_specs_env: tuple[Path, Path]) -> None:
        """Dry-run returns a non-empty list of output lines."""
        specs_dir, vault_specs_dir = temp_specs_env
        lines = dry_run_migration(specs_dir, vault_specs_dir)
        assert len(lines) > 0
        assert any("001 Bootstrap LLM Workbench" in line for line in lines)
        assert any("023 Header API Versioning" in line for line in lines)

    def test_dry_run_shows_artifacts(self, temp_specs_env: tuple[Path, Path]) -> None:
        """Dry-run output includes artifact file moves."""
        specs_dir, vault_specs_dir = temp_specs_env
        lines = dry_run_migration(specs_dir, vault_specs_dir)
        all_output = "\n".join(lines)
        assert "plan.md" in all_output
        assert "tasks.md" in all_output

    def test_dry_run_shows_scaffold_dirs(
        self, temp_specs_env: tuple[Path, Path]
    ) -> None:
        """Dry-run output includes scaffold directory moves."""
        specs_dir, vault_specs_dir = temp_specs_env
        lines = dry_run_migration(specs_dir, vault_specs_dir)
        all_output = "\n".join(lines)
        assert "checklists/" in all_output

    def test_dry_run_no_side_effects(self, temp_specs_env: tuple[Path, Path]) -> None:
        """Dry-run does not create any files or directories."""
        specs_dir, vault_specs_dir = temp_specs_env
        pre_dirs = {str(p) for p in vault_specs_dir.rglob("*") if p.is_dir()}
        dry_run_migration(specs_dir, vault_specs_dir)
        post_dirs = {str(p) for p in vault_specs_dir.rglob("*") if p.is_dir()}
        assert pre_dirs == post_dirs, "Dry-run modified the filesystem"


class TestVerifyMigration:
    """Tests for ``verify_migration``."""

    def test_verify_fails_when_empty(self, temp_specs_env: tuple[Path, Path]) -> None:
        """Verify fails when nothing has been migrated yet."""
        specs_dir, vault_specs_dir = temp_specs_env
        success, missing = verify_migration(specs_dir, vault_specs_dir)
        assert not success
        assert len(missing) == 2  # both spec dirs missing

    def test_verify_passes_after_apply(self, temp_specs_env: tuple[Path, Path]) -> None:
        """Verify passes when all specs are represented in vault."""
        specs_dir, vault_specs_dir = temp_specs_env
        apply_migration(specs_dir, vault_specs_dir, dry_run=False)
        success, missing = verify_migration(specs_dir, vault_specs_dir)
        assert success
        assert len(missing) == 0

    def test_verify_partial_migration(self, temp_specs_env: tuple[Path, Path]) -> None:
        """Verify detects partially migrated specs."""
        specs_dir, vault_specs_dir = temp_specs_env
        # Manually create only one dir
        target = vault_specs_dir / "001 Bootstrap LLM Workbench"
        target.mkdir(parents=True, exist_ok=True)
        (target / "001 Bootstrap LLM Workbench.md").touch()

        success, missing = verify_migration(specs_dir, vault_specs_dir)
        assert not success
        assert len(missing) == 1  # 023 still missing


class TestApplyMigration:
    """Tests for ``apply_migration`` — actual file operations."""

    def test_apply_creates_target_dirs(self, temp_specs_env: tuple[Path, Path]) -> None:
        """Apply creates target directories for each spec."""
        specs_dir, vault_specs_dir = temp_specs_env
        apply_migration(specs_dir, vault_specs_dir, dry_run=False)
        target1 = vault_specs_dir / "001 Bootstrap LLM Workbench"
        target2 = vault_specs_dir / "023 Header API Versioning"
        assert target1.is_dir()
        assert target2.is_dir()

    def test_apply_moves_artifact_files(
        self, temp_specs_env: tuple[Path, Path]
    ) -> None:
        """Apply moves artifact files from specs/ to vault."""
        specs_dir, vault_specs_dir = temp_specs_env
        apply_migration(specs_dir, vault_specs_dir, dry_run=False)
        target = vault_specs_dir / "001 Bootstrap LLM Workbench"
        # Artifact files should exist at target
        assert (target / "001 Bootstrap LLM Workbench - spec.md").exists()
        assert (target / "001 Bootstrap LLM Workbench - plan.md").exists()
        assert (target / "001 Bootstrap LLM Workbench - tasks.md").exists()
        assert (target / "001 Bootstrap LLM Workbench - data-model.md").exists()

    def test_apply_moves_originals(self, temp_specs_env: tuple[Path, Path]) -> None:
        """Apply moves (not copies) — originals no longer in specs/."""
        specs_dir, vault_specs_dir = temp_specs_env
        # Verify original exists
        spec_md_orig = specs_dir / "001-bootstrap-llm-workbench" / "spec.md"
        assert spec_md_orig.exists()
        apply_migration(specs_dir, vault_specs_dir, dry_run=False)
        # Original should be gone (moved)
        assert not spec_md_orig.exists()

    def test_apply_injects_frontmatter(self, temp_specs_env: tuple[Path, Path]) -> None:
        """Apply injects frontmatter into artifact files."""
        specs_dir, vault_specs_dir = temp_specs_env
        apply_migration(specs_dir, vault_specs_dir, dry_run=False)
        target = vault_specs_dir / "001 Bootstrap LLM Workbench"
        moved_spec = target / "001 Bootstrap LLM Workbench - plan.md"
        content = moved_spec.read_text(encoding="utf-8")
        assert content.startswith("---")
        assert "title: 001 Bootstrap LLM Workbench - plan" in content
        assert "type: plan" in content
        assert "- type/spec" in content

    def test_apply_creates_root_index_note(
        self, temp_specs_env: tuple[Path, Path]
    ) -> None:
        """Apply creates a root index note for each spec."""
        specs_dir, vault_specs_dir = temp_specs_env
        apply_migration(specs_dir, vault_specs_dir, dry_run=False)
        target = vault_specs_dir / "001 Bootstrap LLM Workbench"
        root_note = target / "001 Bootstrap LLM Workbench.md"
        assert root_note.exists()
        content = root_note.read_text(encoding="utf-8")
        assert content.startswith("---")
        assert "title: 001 Bootstrap LLM Workbench" in content
        assert "type: spec" in content
        assert "domain/vault" in content
        assert "## Artifacts" in content

    def test_apply_excludes_scaffold_files_from_frontmatter(
        self, temp_specs_env: tuple[Path, Path]
    ) -> None:
        """Scaffold subdir files are moved as-is, no frontmatter."""
        specs_dir, vault_specs_dir = temp_specs_env
        apply_migration(specs_dir, vault_specs_dir, dry_run=False)
        target = vault_specs_dir / "001 Bootstrap LLM Workbench"
        checklist_file = target / "checklists" / "requirements.md"
        assert checklist_file.exists()
        content = checklist_file.read_text(encoding="utf-8")
        assert not content.startswith("---")

    def test_apply_moves_scaffold_subdirs(
        self, temp_specs_env: tuple[Path, Path]
    ) -> None:
        """Scaffold subdirs (checklists, contracts) are moved to vault."""
        specs_dir, vault_specs_dir = temp_specs_env
        apply_migration(specs_dir, vault_specs_dir, dry_run=False)
        target = vault_specs_dir / "001 Bootstrap LLM Workbench"
        assert (target / "checklists").is_dir()
        assert (target / "contracts").is_dir()

    def test_apply_scaffold_originals_moved(
        self, temp_specs_env: tuple[Path, Path]
    ) -> None:
        """Scaffold subdirs are moved, not copied."""
        specs_dir, vault_specs_dir = temp_specs_env
        orig_checklists = specs_dir / "001-bootstrap-llm-workbench" / "checklists"
        assert orig_checklists.exists()
        apply_migration(specs_dir, vault_specs_dir, dry_run=False)
        assert not orig_checklists.exists()

    def test_apply_idempotent(self, temp_specs_env: tuple[Path, Path]) -> None:
        """Running apply twice is safe (idempotent)."""
        specs_dir, vault_specs_dir = temp_specs_env
        apply_migration(specs_dir, vault_specs_dir, dry_run=False)
        apply_migration(specs_dir, vault_specs_dir, dry_run=False)
        target = vault_specs_dir / "001 Bootstrap LLM Workbench"
        assert (target / "001 Bootstrap LLM Workbench - spec.md").exists()
        assert (target / "001 Bootstrap LLM Workbench.md").exists()
        assert (target / "checklists").is_dir()

    def test_apply_spec_only_spec(self, temp_specs_env: tuple[Path, Path]) -> None:
        """Spec 023 (spec.md only) migration works correctly."""
        specs_dir, vault_specs_dir = temp_specs_env
        apply_migration(specs_dir, vault_specs_dir, dry_run=False)
        target = vault_specs_dir / "023 Header API Versioning"
        assert target.is_dir()
        # Only root note + spec.md artifact
        assert (target / "023 Header API Versioning.md").exists()
        assert (target / "023 Header API Versioning - spec.md").exists()
        # No extra artifacts
        assert not (target / "023 Header API Versioning - plan.md").exists()
        # No scaffold dirs
        assert not (target / "checklists").exists()

    def test_migrate_artifact_file_frontmatter_format(self, tmp_path: Path) -> None:
        """_migrate_artifact_file produces correct frontmatter."""
        spec_title = "001 Bootstrap LLM Workbench"
        src = tmp_path / "source" / "plan.md"
        src.parent.mkdir(parents=True)
        src.write_text("# Original Content\n", encoding="utf-8")
        dst = tmp_path / "target" / f"{spec_title} - plan.md"
        dst.parent.mkdir(parents=True)

        _migrate_artifact_file(
            source=src,
            destination=dst,
            spec_title=spec_title,
            artifact_type="plan",
        )
        content = dst.read_text(encoding="utf-8")
        assert content.startswith("---")
        assert "title: 001 Bootstrap LLM Workbench - plan" in content
        assert "type: plan" in content
        assert "spec-refs" in content
        assert "# Original Content" in content

    def test_root_index_note_frontmatter_format(self, tmp_path: Path) -> None:
        """_write_root_index_note produces correct frontmatter."""
        spec_title = "016 SaaS Architecture"
        spec_dir = tmp_path / "specs" / "016-saas-architecture"
        spec_dir.mkdir(parents=True)
        spec_md = spec_dir / "spec.md"
        spec_md.write_text(
            "# Title\n\n**Created**: 2026-06-19\n\n## Clarifications\n\nA test spec.\n",
            encoding="utf-8",
        )
        target_dir = tmp_path / "vault" / "Specs" / spec_title
        target_dir.mkdir(parents=True)

        _write_root_index_note(
            target_dir=target_dir,
            spec_title=spec_title,
            spec_number="016",
            slug="saas-architecture",
            spec_md_content=spec_md.read_text(encoding="utf-8"),
            artifacts=[],
        )
        root_note = target_dir / f"{spec_title}.md"
        assert root_note.exists()
        content = root_note.read_text(encoding="utf-8")
        assert "type: spec" in content
        assert "domain/infrastructure" in content
        assert "title: 016 SaaS Architecture" in content
        assert "status: draft" in content
        assert "created: '2026-06-19'" in content
        assert "## Artifacts" in content

    def test_move_scaffold_dir(self, tmp_path: Path) -> None:
        """_move_scaffold_dir moves directory contents as-is."""
        src = tmp_path / "source" / "checklists"
        dst = tmp_path / "target" / "checklists"
        src.mkdir(parents=True)
        (src / "requirements.md").write_text("# Requirements\n", encoding="utf-8")
        (src / "review.md").write_text("# Review\n", encoding="utf-8")

        _move_scaffold_dir(src, dst)
        assert not src.exists()
        assert dst.is_dir()
        assert (dst / "requirements.md").exists()
        assert (dst / "review.md").exists()


class TestCLIWiring:
    """Tests for the CLI argument parsing."""

    def test_parser_has_migrate_specs(self) -> None:
        """Argument parser has 'migrate-specs' subcommand."""
        import argparse

        from anvil.services.vault.cli import build_parser

        parser = build_parser()
        # Try parsing migrate-specs --dry-run
        args = parser.parse_args(["migrate-specs", "--dry-run"])
        assert args.command == "migrate-specs"
        assert args.dry_run
        assert not args.verify_only
        assert not args.apply

    def test_parser_verify_only(self) -> None:
        """Parser handles --verify-only flag."""
        from anvil.services.vault.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["migrate-specs", "--verify-only"])
        assert args.verify_only
        assert not args.dry_run
        assert not args.apply

    def test_parser_apply(self) -> None:
        """Parser handles --apply flag."""
        from anvil.services.vault.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["migrate-specs", "--apply"])
        assert args.apply
        assert not args.dry_run
        assert not args.verify_only

    def test_parser_default_dirs(self) -> None:
        """Parser has sensible defaults for --vault-dir and --specs-dir."""
        from anvil.services.vault.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["migrate-specs", "--dry-run"])
        assert args.vault_dir == "docs/vault"
        assert args.specs_dir == "specs"

    def test_parser_custom_dirs(self) -> None:
        """Parser accepts custom --vault-dir and --specs-dir."""
        from anvil.services.vault.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(
            [
                "migrate-specs",
                "--dry-run",
                "--vault-dir",
                "/tmp/vault",
                "--specs-dir",
                "/tmp/specs",
            ]
        )
        assert args.vault_dir == "/tmp/vault"
        assert args.specs_dir == "/tmp/specs"

    def test_parser_mutually_exclusive_flags(self) -> None:
        """--dry-run, --verify-only, and --apply are mutually exclusive."""
        from anvil.services.vault.cli import build_parser

        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["migrate-specs", "--dry-run", "--apply"])


# --- Fixtures ---


@pytest.fixture
def temp_specs_env(tmp_path: Path) -> tuple[Path, Path]:
    """Create a temporary specs/ and vault/Specs/ environment.

    Creates two specs: 001-bootstrap-llm-workbench (full) and
    023-header-api-versioning (spec.md only).

    Returns
    -------
    tuple[Path, Path]
        (specs_dir, vault_specs_dir)
    """
    specs_dir = tmp_path / "specs"
    vault_specs_dir = tmp_path / "vault" / "Specs"
    vault_specs_dir.mkdir(parents=True)

    # --- 001-bootstrap-llm-workbench (full) ---
    spec001 = specs_dir / "001-bootstrap-llm-workbench"
    spec001.mkdir(parents=True)

    # spec.md with **Created** date
    spec001_md = (
        "# Feature Specification: Bootstrap LLM Workbench\n"
        "\n"
        "**Feature Branch**: `001-bootstrap-llm-workbench`  \n"
        "**Created**: 2026-06-20  \n"
        "**Status**: Draft  \n"
        "\n"
        "## Clarifications\n"
        "\n"
        "### Session 2026-06-20\n"
        "\n"
        "- Q1: Question? → A: Answer.\n"
    )
    (spec001 / "spec.md").write_text(spec001_md, encoding="utf-8")

    # plan.md
    (spec001 / "plan.md").write_text(
        "# Plan\n\nImplementation plan.\n", encoding="utf-8"
    )
    # tasks.md
    (spec001 / "tasks.md").write_text("- [ ] Task 1\n- [ ] Task 2\n", encoding="utf-8")
    # data-model.md
    (spec001 / "data-model.md").write_text(
        "# Data Model\n\nEntity definitions.\n", encoding="utf-8"
    )
    # research.md
    (spec001 / "research.md").write_text("# Research\n\nFindings.\n", encoding="utf-8")
    # quickstart.md
    (spec001 / "quickstart.md").write_text(
        "# Quickstart\n\nHow to start.\n", encoding="utf-8"
    )

    # checklists/
    (spec001 / "checklists").mkdir()
    (spec001 / "checklists" / "requirements.md").write_text(
        "- [ ] Requirement A\n", encoding="utf-8"
    )
    # contracts/
    (spec001 / "contracts").mkdir()
    (spec001 / "contracts" / "api.md").write_text("# API Contract\n", encoding="utf-8")

    # --- 023-header-api-versioning (spec.md only) ---
    spec023 = specs_dir / "023-header-api-versioning"
    spec023.mkdir(parents=True)
    spec023_md = (
        "# Feature Specification: Header-Based API Versioning\n"
        "\n"
        "**Created**: 2026-06-21  \n"
        "**Status**: Draft  \n"
        "\n"
        "## Clarifications\n"
        "\n"
        "A spec about API versioning.\n"
    )
    (spec023 / "spec.md").write_text(spec023_md, encoding="utf-8")

    return specs_dir, vault_specs_dir
