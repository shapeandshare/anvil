"""Unit tests for anvil/services/vault/migrate_specs.py.

Tests pure functions (slug_to_title, parse_spec_number_and_slug, assign_domain,
parse_created_date, extract_summary) and I/O operations (build_migration_plan,
_migrate_artifact_file, _write_root_index_note, _move_scaffold_dir, etc.)
using temporary directories.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.services.vault.migrate_specs import (
    _fix_existing_files,
    _migrate_artifact_file,
    _move_scaffold_dir,
    _write_root_index_note,
    apply_migration,
    assign_domain,
    build_migration_plan,
    dry_run_migration,
    extract_summary,
    parse_created_date,
    parse_spec_number_and_slug,
    slug_to_title,
    spec_dirname_to_title,
    verify_migration,
)

##############################################################################
# slug_to_title
##############################################################################


def test_slug_to_title_simple() -> None:
    """Simple kebab-case slug converts to Title Case."""
    assert slug_to_title("bootstrap-llm-workbench") == "Bootstrap LLM Workbench"


def test_slug_to_title_with_acronyms() -> None:
    """Words matching ACRONYM_MAP use the mapped value."""
    assert slug_to_title("api-ux-enhancement") == "API UX Enhancement"


def test_slug_to_title_single_word() -> None:
    """A single word converts to title case without spaces."""
    assert slug_to_title("hello") == "Hello"


def test_slug_to_title_all_acronyms() -> None:
    """All words being acronyms gets mapped correctly."""
    assert slug_to_title("api-ui-db") == "API UI DB"


def test_slug_to_title_mixed_case_input() -> None:
    """Input with mixed case is lower-cased before lookup."""
    assert slug_to_title("API-UX-Refactor") == "API UX Refactor"


def test_slug_to_title_mlflow() -> None:
    """'mlflow' maps to 'MLflow' (special casing)."""
    assert slug_to_title("mlflow-tracking") == "MLflow Tracking"


def test_slug_to_title_e2e() -> None:
    """'e2e' maps to 'E2E'."""
    assert slug_to_title("e2e-testing") == "E2E Testing"


##############################################################################
# parse_spec_number_and_slug
##############################################################################


def test_parse_spec_number_and_slug_valid() -> None:
    """A valid NNN-slug dirname returns (number, slug)."""
    num, slug = parse_spec_number_and_slug("001-bootstrap-llm-workbench")
    assert num == "001"
    assert slug == "bootstrap-llm-workbench"


def test_parse_spec_number_and_slug_no_prefix() -> None:
    """A dirname without NNN- prefix raises ValueError."""
    with pytest.raises(ValueError, match="Invalid spec directory name"):
        parse_spec_number_and_slug("bootstrap-llm-workbench")


def test_parse_spec_number_and_slug_too_short() -> None:
    """A too-short dirname raises ValueError."""
    with pytest.raises(ValueError, match="Invalid spec directory name"):
        parse_spec_number_and_slug("01-foo")


def test_parse_spec_number_and_slug_empty() -> None:
    """An empty string raises ValueError."""
    with pytest.raises(ValueError):
        parse_spec_number_and_slug("")


def test_parse_spec_number_and_slug_only_number() -> None:
    """A number-only dirname raises ValueError."""
    with pytest.raises(ValueError, match="Invalid spec directory name"):
        parse_spec_number_and_slug("001")


##############################################################################
# spec_dirname_to_title
##############################################################################


def test_spec_dirname_to_title() -> None:
    """Full spec dirname converts to 'NNN Title Case'."""
    assert (
        spec_dirname_to_title("001-bootstrap-llm-workbench")
        == "001 Bootstrap LLM Workbench"
    )


def test_spec_dirname_to_title_with_acronym() -> None:
    """Acronym overrides apply to spec titles."""
    assert spec_dirname_to_title("042-api-ux-enhancement") == "042 API UX Enhancement"


##############################################################################
# assign_domain
##############################################################################


def test_assign_domain_core() -> None:
    """Keywords 'core', 'model', 'engine', 'training' map to domain/core."""
    assert assign_domain("core-engine") == "domain/core"
    assert assign_domain("model-training") == "domain/core"


def test_assign_domain_training_data() -> None:
    """'dataset', 'data', 'corpus' map to domain/training."""
    assert assign_domain("dataset-import") == "domain/training"
    assert assign_domain("data-pipeline") == "domain/training"
    assert assign_domain("corpus-curation") == "domain/training"


def test_assign_domain_ui() -> None:
    """'ui', 'frontend', 'ux' map to domain/ui."""
    assert assign_domain("ui-dashboard") == "domain/ui"
    assert assign_domain("frontend-components") == "domain/ui"
    assert assign_domain("ux-enhancement") == "domain/ui"


def test_assign_domain_infrastructure() -> None:
    """'saas', 'infrastructure', 'docker', 'deploy' map to domain/infrastructure."""
    assert assign_domain("saas-deployment") == "domain/infrastructure"
    assert assign_domain("infrastructure-setup") == "domain/infrastructure"
    assert assign_domain("docker-compose") == "domain/infrastructure"
    assert assign_domain("deploy-pipeline") == "domain/infrastructure"


def test_assign_domain_tracking() -> None:
    """'experiment', 'tracking', 'mlflow' map to domain/tracking."""
    assert assign_domain("experiment-tracking") == "domain/tracking"
    assert assign_domain("mlflow-setup") == "domain/tracking"


def test_assign_domain_tooling() -> None:
    """'release', 'version', 'ci' map to domain/tooling."""
    assert assign_domain("release-workflow") == "domain/tooling"
    assert assign_domain("version-bump") == "domain/tooling"
    assert assign_domain("ci-pipeline") == "domain/tooling"


def test_assign_domain_governance() -> None:
    """'content', 'governance' map to domain/governance."""
    assert assign_domain("content-strategy") == "domain/governance"
    assert assign_domain("governance-model") == "domain/governance"


def test_assign_domain_default() -> None:
    """Unknown keywords default to domain/vault."""
    assert assign_domain("random-topic") == "domain/vault"


def test_assign_domain_prefers_longer_keyword() -> None:
    """Longer keyword matches are preferred over shorter substring matches."""
    # 'data' is in 'governance data' but 'governance' is longer
    assert assign_domain("governance-data") == "domain/governance"


##############################################################################
# parse_created_date
##############################################################################


def test_parse_created_date_found() -> None:
    """A **Created**: line with ISO date returns the date."""
    content = "Some text\n**Created**: 2024-06-15\nMore text."
    assert parse_created_date(content) == "2024-06-15"


def test_parse_created_date_not_found() -> None:
    """Missing **Created** line returns empty string."""
    content = "No date here."
    assert parse_created_date(content) == ""


def test_parse_created_date_empty_content() -> None:
    """Empty content returns empty string."""
    assert parse_created_date("") == ""


def test_parse_created_date_different_format() -> None:
    """A non-date after **Created**: does not match the pattern."""
    content = "**Created**: NotADate"
    assert parse_created_date(content) == ""


##############################################################################
# extract_summary
##############################################################################


def test_extract_summary_from_clarifications() -> None:
    """Extract summary from ## Clarifications section."""
    content = """# Title

## Clarifications

This is the summary text.

- Some detail item
"""
    assert extract_summary(content) == "This is the summary text."


def test_extract_summary_fallback_first_paragraph() -> None:
    """Fall back to first non-heading, non-metadata paragraph."""
    content = "# Title\n**Metadata**: stuff\n\nThis is the first real paragraph."
    assert extract_summary(content) == "This is the first real paragraph."


def test_extract_summary_empty() -> None:
    """Empty content returns empty string."""
    assert extract_summary("") == ""


def test_extract_summary_only_headings() -> None:
    """Content with only headings returns empty string."""
    content = "# Title\n## Section\n### Subsection"
    assert extract_summary(content) == ""


def test_extract_summary_clarifications_skip_h3() -> None:
    """Skip ### lines inside Clarifications section."""
    content = "## Clarifications\n\n### Sub-header\n\nThis is the summary."
    assert extract_summary(content) == "This is the summary."


def test_extract_summary_clarifications_skip_dash_lines() -> None:
    """Skip dash-list lines inside Clarifications section."""
    content = "## Clarifications\n\n- list item\n\nActual summary."
    assert extract_summary(content) == "Actual summary."


##############################################################################
# build_migration_plan
##############################################################################


def test_build_migration_plan_no_specs_dir(tmp_path: Path) -> None:
    """Non-existent specs dir yields empty plan."""
    specs = tmp_path / "specs"
    vault_specs = tmp_path / "vault" / "Specs"
    plan = build_migration_plan(specs, vault_specs)
    assert plan == []


def test_build_migration_plan_empty_specs_dir(tmp_path: Path) -> None:
    """Empty specs dir yields empty plan."""
    specs = tmp_path / "specs"
    specs.mkdir(parents=True)
    vault_specs = tmp_path / "vault" / "Specs"
    plan = build_migration_plan(specs, vault_specs)
    assert plan == []


def test_build_migration_plan_basic(tmp_path: Path) -> None:
    """A single valid spec dir produces a plan entry."""
    specs = tmp_path / "specs"
    spec_dir = specs / "001-bootstrap-llm"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# Spec")
    (spec_dir / "plan.md").write_text("# Plan")
    vault_specs = tmp_path / "vault" / "Specs"

    plan = build_migration_plan(specs, vault_specs)
    assert len(plan) == 1

    entry = plan[0]
    assert entry["title"] == "001 Bootstrap LLM"
    assert entry["number"] == "001"
    assert entry["slug"] == "bootstrap-llm"
    assert entry["has_spec_md"] is True
    assert len(entry["artifacts"]) == 2


def test_build_migration_plan_skips_non_spec_dirs(tmp_path: Path) -> None:
    """Directories not matching NNN-slug are skipped."""
    specs = tmp_path / "specs"
    (specs / "not-a-spec").mkdir(parents=True)
    (specs / "also-invalid").mkdir()
    vault_specs = tmp_path / "vault" / "Specs"

    plan = build_migration_plan(specs, vault_specs)
    assert plan == []


def test_build_migration_plan_with_scaffold(tmp_path: Path) -> None:
    """Scaffold subdirectories appear in plan, not as artifacts."""
    specs = tmp_path / "specs"
    spec_dir = specs / "001-foo"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("x")
    (spec_dir / "checklists" / "tasks.md").parent.mkdir()
    (spec_dir / "checklists" / "tasks.md").write_text("tasks")
    (spec_dir / "contracts" / "agreement.md").parent.mkdir()
    (spec_dir / "contracts" / "agreement.md").write_text("agree")
    vault_specs = tmp_path / "vault" / "Specs"

    plan = build_migration_plan(specs, vault_specs)
    assert len(plan) == 1
    entry = plan[0]
    # Artifacts should only contain spec.md (not scaffold files)
    artifact_types = [a["type"] for a in entry["artifacts"]]
    assert artifact_types == ["spec"]
    assert len(entry["scaffold_dirs"]) == 2


def test_build_migration_plan_multiple_specs(tmp_path: Path) -> None:
    """Multiple spec dirs produce multiple plan entries in sorted order."""
    specs = tmp_path / "specs"
    (specs / "002-bar").mkdir(parents=True)
    (specs / "002-bar" / "spec.md").write_text("x")
    (specs / "001-foo").mkdir()
    (specs / "001-foo" / "spec.md").write_text("x")
    vault_specs = tmp_path / "vault" / "Specs"

    plan = build_migration_plan(specs, vault_specs)
    assert len(plan) == 2
    assert plan[0]["number"] == "001"
    assert plan[1]["number"] == "002"


##############################################################################
# _migrate_artifact_file
##############################################################################


def test_migrate_artifact_file_creates_file(tmp_path: Path) -> None:
    """_migrate_artifact_file moves a source file to destination with frontmatter."""
    src = tmp_path / "specs" / "spec.md"
    src.parent.mkdir(parents=True)
    src.write_text("Original body text.")
    dst = tmp_path / "vault" / "Specs" / "001 Foo" / "001 Foo - spec.md"
    dst.parent.mkdir(parents=True)

    _migrate_artifact_file(src, dst, "001 Foo", "spec")

    assert dst.exists()
    content = dst.read_text()
    assert "title: 001 Foo - spec" in content
    assert "type: spec" in content
    assert "Original body text" in content
    # Source should be removed
    assert not src.exists()


def test_migrate_artifact_file_destination_exists(tmp_path: Path) -> None:
    """If destination exists, source is removed and no write occurs."""
    src = tmp_path / "spec.md"
    src.write_text("Original")
    dst = tmp_path / "dest.md"
    dst.write_text("Existing")
    _migrate_artifact_file(src, dst, "001 Foo", "spec")
    assert dst.read_text() == "Existing"
    assert not src.exists()


def test_migrate_artifact_file_missing_source(tmp_path: Path) -> None:
    """If source is missing, nothing happens."""
    src = tmp_path / "missing.md"
    dst = tmp_path / "dest.md"
    _migrate_artifact_file(src, dst, "001 Foo", "spec")
    assert not dst.exists()


##############################################################################
# _write_root_index_note
##############################################################################


def test_write_root_index_note_creates_file(tmp_path: Path) -> None:
    """_write_root_index_note creates the root index note with frontmatter."""
    target = tmp_path / "vault" / "Specs" / "001 Foo"
    spec_md_content = "**Created**: 2024-06-15\n\nSummary para."
    _write_root_index_note(
        target_dir=target,
        spec_title="001 Foo",
        spec_number="001",
        slug="foo",
        spec_md_content=spec_md_content,
        artifacts=[{"filename": "001 Foo - spec.md", "type": "spec"}],
    )

    root = target / "001 Foo.md"
    assert root.exists()
    content = root.read_text()
    assert "title: 001 Foo" in content
    assert "type: spec" in content
    assert "domain/vault" in content  # 'foo' doesn't match keywords
    assert "created: '2024-06-15'" in content
    assert "## Summary" in content
    assert "Summary para." in content
    assert "## Artifacts" in content
    assert "[[001 Foo - spec|spec]]" in content
    assert "## References" in content


def test_write_root_index_note_skips_if_exists(tmp_path: Path) -> None:
    """If root note already exists, it is not overwritten."""
    target = tmp_path / "vault" / "Specs" / "001 Foo"
    target.mkdir(parents=True)
    root = target / "001 Foo.md"
    root.write_text("Existing content.")

    _write_root_index_note(
        target_dir=target,
        spec_title="001 Foo",
        spec_number="001",
        slug="foo",
        spec_md_content="",
        artifacts=[],
    )

    assert root.read_text() == "Existing content."


def test_write_root_index_note_no_summary(tmp_path: Path) -> None:
    """If no summary can be extracted, Summary section is omitted."""
    target = tmp_path / "vault" / "Specs" / "001 Bar"
    _write_root_index_note(
        target_dir=target,
        spec_title="001 Bar",
        spec_number="001",
        slug="bar",
        spec_md_content="",
        artifacts=[],
    )

    content = (target / "001 Bar.md").read_text()
    assert "## Summary" not in content
    assert "_(No artifacts migrated.)_" in content


def test_write_root_index_note_no_created_date(tmp_path: Path) -> None:
    """Missing created date in spec.md results in 'created: ~'."""
    target = tmp_path / "vault" / "Specs" / "001 Baz"
    _write_root_index_note(
        target_dir=target,
        spec_title="001 Baz",
        spec_number="001",
        slug="baz",
        spec_md_content="No date here.",
        artifacts=[],
    )

    content = (target / "001 Baz.md").read_text()
    assert "created: ~" in content


##############################################################################
# _move_scaffold_dir
##############################################################################


def test_move_scaffold_dir_moves(tmp_path: Path) -> None:
    """_move_scaffold_dir moves a directory to the target."""
    src = tmp_path / "checklists"
    src.mkdir(parents=True)
    (src / "tasks.md").write_text("tasks")
    dst_parent = tmp_path / "vault" / "Specs" / "001 Foo"
    dst = dst_parent / "checklists"

    _move_scaffold_dir(src, dst)

    assert dst.exists()
    assert (dst / "tasks.md").exists()
    assert not src.exists()


def test_move_scaffold_dir_source_missing(tmp_path: Path) -> None:
    """If source doesn't exist, nothing happens."""
    src = tmp_path / "missing"
    dst = tmp_path / "dest"
    _move_scaffold_dir(src, dst)
    assert not dst.exists()


def test_move_scaffold_dir_destination_exists(tmp_path: Path) -> None:
    """If destination exists, source is removed."""
    src = tmp_path / "src_checklists"
    src.mkdir()
    (src / "old.md").write_text("old")
    dst = tmp_path / "dst_checklists"
    dst.mkdir()
    (dst / "existing.md").write_text("existing")

    _move_scaffold_dir(src, dst)

    assert dst.exists()
    assert (dst / "existing.md").exists()
    assert not src.exists()


##############################################################################
# _fix_existing_files
##############################################################################


def test_fix_existing_files_no_specs_dir(tmp_path: Path) -> None:
    """If vault Specs dir doesn't exist, nothing happens (no crash)."""
    vault_specs = tmp_path / "vault" / "Specs"
    _fix_existing_files(vault_specs)  # should not raise


def test_fix_existing_files_fixes_dates(tmp_path: Path) -> None:
    """_fix_existing_files replaces '' with ~ for created/updated."""
    spec_dir = tmp_path / "Specs" / "001 Foo"
    spec_dir.mkdir(parents=True)
    art = spec_dir / "001 Foo - spec.md"
    art.write_text("---\ncreated: ''\nupdated: ''\n---\nbody")

    _fix_existing_files(tmp_path / "Specs")

    content = art.read_text()
    assert "created: ~" in content
    assert "updated: ~" in content


def test_fix_existing_files_fixes_root_note_wikilinks(tmp_path: Path) -> None:
    """_fix_existing_files strips .md suffix from wikilinks in root notes."""
    spec_dir = tmp_path / "Specs" / "001 Foo"
    spec_dir.mkdir(parents=True)
    root = spec_dir / "001 Foo.md"
    root.write_text("[[001 Foo - spec.md|spec]]")

    _fix_existing_files(tmp_path / "Specs")

    content = root.read_text()
    assert "[[001 Foo - spec|spec]]" in content
    assert "[[001 Foo - spec.md|spec]]" not in content


def test_fix_existing_files_skips_root_note_without_md_links(tmp_path: Path) -> None:
    """Root notes without .md wikilinks are unchanged."""
    spec_dir = tmp_path / "Specs" / "001 Foo"
    spec_dir.mkdir(parents=True)
    root = spec_dir / "001 Foo.md"
    root.write_text("[[Other Note]]")
    original = root.read_text()
    _fix_existing_files(tmp_path / "Specs")
    assert root.read_text() == original


##############################################################################
# dry_run_migration
##############################################################################


def test_dry_run_migration_output(tmp_path: Path) -> None:
    """dry_run_migration produces readable lines."""
    specs = tmp_path / "specs"
    spec_dir = specs / "001-bootstrap-llm"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# Spec")
    vault_specs = tmp_path / "vault" / "Specs"

    lines = dry_run_migration(specs, vault_specs)
    assert "Migration Plan" in lines[0]
    assert "001 Bootstrap LLM" in " ".join(lines)
    assert "Total: 1 spec(s)" in lines[-1]


def test_dry_run_migration_empty(tmp_path: Path) -> None:
    """Empty specs dir produces minimal output."""
    specs = tmp_path / "specs"
    specs.mkdir()
    vault_specs = tmp_path / "vault" / "Specs"
    lines = dry_run_migration(specs, vault_specs)
    assert "Total: 0 spec(s)" in lines[-1]


##############################################################################
# verify_migration
##############################################################################


def test_verify_migration_all_present(tmp_path: Path) -> None:
    """verify_migration returns True when all specs are migrated."""
    specs = tmp_path / "specs"
    spec_dir = specs / "001-foo"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("x")
    vault_specs = tmp_path / "vault" / "Specs"
    # Create the root note that would be written by migration
    target_dir = vault_specs / "001 Foo"
    target_dir.mkdir(parents=True)
    (target_dir / "001 Foo.md").write_text("Done")

    success, missing = verify_migration(specs, vault_specs)
    assert success is True
    assert missing == []


def test_verify_migration_missing(tmp_path: Path) -> None:
    """verify_migration returns False when a spec is not migrated."""
    specs = tmp_path / "specs"
    spec_dir = specs / "001-foo"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("x")
    vault_specs = tmp_path / "vault" / "Specs"

    success, missing = verify_migration(specs, vault_specs)
    assert success is False
    assert "001 Foo" in missing


##############################################################################
# apply_migration (dry_run)
##############################################################################


def test_apply_migration_dry_run(tmp_path: Path) -> None:
    """apply_migration with dry_run=True does not modify filesystem."""
    specs = tmp_path / "specs"
    spec_dir = specs / "001-foo"
    spec_dir.mkdir(parents=True)
    spec_md = spec_dir / "spec.md"
    spec_md.write_text("# Spec\n**Created**: 2024-06-15\n\nSummary.")
    vault_specs = tmp_path / "vault" / "Specs"

    apply_migration(specs, vault_specs, dry_run=True)

    # Source file should still exist
    assert spec_md.exists()
    # No vault dir should be created
    assert not vault_specs.exists()


##############################################################################
# apply_migration (full)
##############################################################################


def test_apply_migration_full(tmp_path: Path) -> None:
    """apply_migration with dry_run=False performs the migration."""
    specs = tmp_path / "specs"
    spec_dir = specs / "001-bootstrap-llm"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text(
        "# Spec\n**Created**: 2024-06-15\n\nSummary text."
    )
    (spec_dir / "plan.md").write_text("# Plan")
    (spec_dir / "checklists" / "tasks.md").parent.mkdir()
    (spec_dir / "checklists" / "tasks.md").write_text("# Tasks")

    vault_specs = tmp_path / "vault" / "Specs"
    apply_migration(specs, vault_specs, dry_run=False)

    # Check target structure
    target = vault_specs / "001 Bootstrap LLM"
    assert target.exists()
    assert (target / "001 Bootstrap LLM.md").exists()
    assert (target / "001 Bootstrap LLM - spec.md").exists()
    assert (target / "001 Bootstrap LLM - plan.md").exists()
    assert (target / "checklists" / "tasks.md").exists()

    # Source files should be removed
    assert not (spec_dir / "spec.md").exists()
    assert not (spec_dir / "plan.md").exists()
    assert not (spec_dir / "checklists").exists()


def test_apply_migration_with_no_spec_md(tmp_path: Path) -> None:
    """apply_migration works even when spec.md is missing."""
    specs = tmp_path / "specs"
    spec_dir = specs / "001-foo"
    spec_dir.mkdir(parents=True)
    (spec_dir / "plan.md").write_text("# Plan")
    vault_specs = tmp_path / "vault" / "Specs"

    apply_migration(specs, vault_specs, dry_run=False)

    target = vault_specs / "001 Foo"
    assert (target / "001 Foo.md").exists()
    assert (target / "001 Foo - plan.md").exists()
