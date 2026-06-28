# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Migrate ``specs/`` artifacts into ``docs/vault/Specs/``.

Provides the logic for the ``anvil-vault migrate-specs`` subcommand,
supporting ``--dry-run``, ``--verify-only``, and ``--apply`` modes.

The migration converts kebab-case spec directory names
(``specs/NNN-slug-words/``) into Title Case vault directories
(``docs/vault/Specs/NNN Title Case Words/``), applies acronym
overrides, injects frontmatter into artifact files, creates
root index notes, and moves scaffold subdirectories as-is.
"""

from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACRONYM_MAP: dict[str, str] = {
    "saas": "SaaS",
    "owasp": "OWASP",
    "mlflow": "MLflow",
    "cli": "CLI",
    "ui": "UI",
    "ux": "UX",
    "tls": "TLS",
    "api": "API",
    "dx": "DX",
    "db": "DB",
    "lakefs": "LakeFS",
    "llm": "LLM",
    "df": "DF",
    "lfs": "LFS",
    "md": "MD",
    "e2e": "E2E",
    "gc": "GC",
}

ARTIFACT_TYPES: dict[str, str] = {
    "spec.md": "spec",
    "plan.md": "plan",
    "tasks.md": "tasks",
    "data-model.md": "data-model",
    "research.md": "research",
    "quickstart.md": "quickstart",
}

SCAFFOLD_DIRS: set[str] = {"checklists", "contracts"}

# Domain tag constants (SonarCloud S1192: deduplicated)
_DOMAIN_CORE = "domain/core"
_DOMAIN_TRAINING = "domain/training"
_DOMAIN_UI = "domain/ui"
_DOMAIN_INFRA = "domain/infrastructure"
_DOMAIN_TRACKING = "domain/tracking"
_DOMAIN_TOOLING = "domain/tooling"
_DOMAIN_GOV = "domain/governance"
_DOMAIN_VAULT = "domain/vault"

DOMAIN_KEYWORDS: dict[str, str] = {
    "core": _DOMAIN_CORE,
    "model": _DOMAIN_CORE,
    "engine": _DOMAIN_CORE,
    "training": _DOMAIN_CORE,
    "dataset": _DOMAIN_TRAINING,
    "data": _DOMAIN_TRAINING,
    "corpus": _DOMAIN_TRAINING,
    "ui": _DOMAIN_UI,
    "frontend": _DOMAIN_UI,
    "ux": _DOMAIN_UI,
    "saas": _DOMAIN_INFRA,
    "infrastructure": _DOMAIN_INFRA,
    "docker": _DOMAIN_INFRA,
    "deploy": _DOMAIN_INFRA,
    "experiment": _DOMAIN_TRACKING,
    "tracking": _DOMAIN_TRACKING,
    "mlflow": _DOMAIN_TRACKING,
    "release": _DOMAIN_TOOLING,
    "version": _DOMAIN_TOOLING,
    "ci": _DOMAIN_TOOLING,
    "content": _DOMAIN_GOV,
    "governance": _DOMAIN_GOV,
}

# YAML null date marker (SonarCloud S1192: deduplicated)
_YAML_NULL_DATE = "created: ~"
_YAML_NULL_UPDATED = "updated: ~"

# ---------------------------------------------------------------------------
# Pure functions (testable, no I/O)
# ---------------------------------------------------------------------------


def slug_to_title(slug: str) -> str:
    """Convert a kebab-case slug to Title Case with acronym overrides.

    Each hyphen-delimited word is title-cased individually. Words
    matching a key in :data:`ACRONYM_MAP` use the mapped value instead.

    Parameters
    ----------
    slug : str
        The slug portion after ``NNN-`` (e.g. ``"bootstrap-llm-workbench"``).

    Returns
    -------
    str
        Title-cased string with acronym overrides applied.
    """
    parts = slug.split("-")
    titled: list[str] = []
    for part in parts:
        lower = part.lower()
        if lower in ACRONYM_MAP:
            titled.append(ACRONYM_MAP[lower])
        else:
            titled.append(part.title())
    return " ".join(titled)


def parse_spec_number_and_slug(dirname: str) -> tuple[str, str]:
    """Extract spec number and slug from a ``specs/`` directory name.

    Parameters
    ----------
    dirname : str
        Directory name like ``"001-bootstrap-llm-workbench"``.

    Returns
    -------
    tuple[str, str]
        ``(number, slug)`` e.g. ``("001", "bootstrap-llm-workbench")``.

    Raises
    ------
    ValueError
        If the directory name does not match the ``NNN-slug`` pattern.
    """
    match = re.match(r"^(\d{3})-(.+)$", dirname)
    if not match:
        raise ValueError(f"Invalid spec directory name: {dirname}")
    return match.group(1), match.group(2)


def spec_dirname_to_title(dirname: str) -> str:
    """Convert a spec directory name to its vault title.

    Parameters
    ----------
    dirname : str
        Directory name like ``"001-bootstrap-llm-workbench"``.

    Returns
    -------
    str
        Title like ``"001 Bootstrap LLM Workbench"``.
    """
    num, slug = parse_spec_number_and_slug(dirname)
    return f"{num} {slug_to_title(slug)}"


def assign_domain(slug: str) -> str:
    """Assign a domain tag based on keywords in the slug.

    Checks longer (more specific) keywords first to avoid false
    positives from short substrings (e.g. "data" in "governance").

    Parameters
    ----------
    slug : str
        The slug portion after ``NNN-``.

    Returns
    -------
    str
        Domain tag like ``"domain/core"``. Defaults to ``"domain/vault"``.
    """
    slug_lower = slug.lower()
    # Check longest keywords first to prefer specific matches
    for keyword in sorted(DOMAIN_KEYWORDS, key=len, reverse=True):
        if keyword in slug_lower:
            return DOMAIN_KEYWORDS[keyword]
    return "domain/vault"


def parse_created_date(spec_md_content: str) -> str:
    """Parse the ``**Created**:`` date line from spec.md content.

    Parameters
    ----------
    spec_md_content : str
        Raw content of a ``spec.md`` file.

    Returns
    -------
    str
        ISO date string (``YYYY-MM-DD``) or empty string if not found.
    """
    match = re.search(r"\*\*Created\*\*:\s*(\d{4}-\d{2}-\d{2})", spec_md_content)
    if match:
        return match.group(1)
    return ""


def extract_summary(spec_md_content: str) -> str:
    """Extract a brief Summary paragraph from spec.md content.

    Tries the ``## Clarifications`` section first, then falls back
    to the first non-heading, non-metadata paragraph.

    Parameters
    ----------
    spec_md_content : str
        Raw content of a ``spec.md`` file.

    Returns
    -------
    str
        Extracted summary text, or empty string if none found.
    """
    # Try ## Clarifications section
    clar_match = re.search(
        r"## Clarifications\s*\n+(.*?)(?:\n##|\Z)", spec_md_content, re.DOTALL
    )
    if clar_match:
        text = clar_match.group(1).strip()
        lines = text.split("\n")
        for line in lines:
            stripped = line.strip()
            if (
                stripped
                and not stripped.startswith("###")
                and not stripped.startswith("-")
            ):
                return stripped

    # Fall back to first non-metadata paragraph
    for line in spec_md_content.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("**"):
            return stripped

    return ""


# ---------------------------------------------------------------------------
# Plan building
# ---------------------------------------------------------------------------


def build_migration_plan(
    specs_dir: Path, vault_specs_dir: Path
) -> list[dict[str, object]]:
    """Build a migration plan for all spec directories.

    Scans ``specs_dir`` for matching ``NNN-slug`` directories and
    produces a list of plan entries describing what to migrate.

    Parameters
    ----------
    specs_dir : Path
        Path to the ``specs/`` directory.
    vault_specs_dir : Path
        Path to the ``docs/vault/Specs/`` directory.

    Returns
    -------
    list[dict[str, object]]
        List of migration plan entries, each containing keys:
        ``source``, ``target_dir``, ``title``, ``number``, ``slug``,
        ``artifacts`` (list of dicts), ``scaffold_dirs`` (list of dicts),
        ``root_note_path``, ``has_spec_md``, ``spec_md_source``,
        and ``spec_md_content``.
    """
    plan: list[dict[str, object]] = []

    if not specs_dir.exists():
        return plan

    for spec_dir in sorted(specs_dir.iterdir()):
        if not spec_dir.is_dir():
            continue
        entry = _build_spec_plan_entry(spec_dir, vault_specs_dir)
        if entry is not None:
            plan.append(entry)

    return plan


def _build_spec_plan_entry(
    spec_dir: Path, vault_specs_dir: Path
) -> dict[str, object] | None:
    """Build a single migration plan entry for one spec directory.

    Parameters
    ----------
    spec_dir : Path
        Path to the spec directory in ``specs/``.
    vault_specs_dir : Path
        Path to the ``docs/vault/Specs/`` directory.

    Returns
    -------
    dict or None
        Plan entry dict, or ``None`` if the directory doesn't match
        the ``NNN-slug`` pattern.
    """
    dirname = spec_dir.name
    try:
        num, slug = parse_spec_number_and_slug(dirname)
    except ValueError:
        return None

    title = spec_dirname_to_title(dirname)
    vault_spec_dir = vault_specs_dir / title

    entry: dict[str, object] = {
        "source": str(spec_dir),
        "target_dir": str(vault_spec_dir),
        "title": title,
        "number": num,
        "slug": slug,
        "artifacts": [],
        "scaffold_dirs": [],
        "root_note_path": str(vault_spec_dir / f"{title}.md"),
        "has_spec_md": False,
        "spec_md_source": "",
        "spec_md_content": "",
    }

    # Collect artifact files
    for fname in sorted(ARTIFACT_TYPES):
        src = spec_dir / fname
        if src.exists():
            artifact_type = ARTIFACT_TYPES[fname]
            dest_name = f"{title} - {fname}"
            artifacts = entry["artifacts"]
            assert isinstance(artifacts, list)
            artifacts.append(
                {
                    "source": str(src),
                    "target": str(vault_spec_dir / dest_name),
                    "type": artifact_type,
                    "filename": dest_name,
                }
            )

    # Load spec.md content for root index note generation
    spec_md = spec_dir / "spec.md"
    if spec_md.exists():
        entry["has_spec_md"] = True
        entry["spec_md_source"] = str(spec_md)
        entry["spec_md_content"] = spec_md.read_text(encoding="utf-8")

    # Collect scaffold subdirectories
    for sdir in SCAFFOLD_DIRS:
        src_dir = spec_dir / sdir
        if src_dir.exists() and src_dir.is_dir():
            scaffold_dirs = entry["scaffold_dirs"]
            assert isinstance(scaffold_dirs, list)
            scaffold_dirs.append(
                {
                    "source": str(src_dir),
                    "target": str(vault_spec_dir / sdir),
                }
            )

    return entry


# ---------------------------------------------------------------------------
# Artifact and index-note writing (filesystem I/O)
# ---------------------------------------------------------------------------


def _migrate_artifact_file(
    source: Path,
    destination: Path,
    spec_title: str,
    artifact_type: str,
) -> None:
    """Move a single artifact file to its vault destination with frontmatter.

    Reads the source file, prepends YAML frontmatter, and writes to
    the destination. The source file is removed after a successful read.

    Parameters
    ----------
    source : Path
        Source path in ``specs/``.
    destination : Path
        Destination path in ``docs/vault/Specs/``.
    spec_title : str
        The spec title (e.g. ``"001 Bootstrap LLM Workbench"``).
    artifact_type : str
        Type from :data:`ARTIFACT_TYPES` (e.g. ``"plan"``, ``"spec"``).
    """
    if not source.exists():
        return
    if destination.exists():
        # Already migrated; remove source if still present
        if source.exists():
            source.unlink()
        return

    original_content = source.read_text(encoding="utf-8")

    # YAML frontmatter for artifact files
    frontmatter_lines = [
        "---",
        f"title: {spec_title} - {artifact_type}",
        f"type: {artifact_type}",
        "tags:",
        "  - type/spec",
        "spec-refs:",
        f"  - docs/vault/Specs/{spec_title}/",
        "related:",
        f"  - '[[{spec_title}]]'",
        "created: ~",
        "updated: ~",
        "---",
    ]

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "\n".join(frontmatter_lines) + "\n" + original_content,
        encoding="utf-8",
    )
    source.unlink()


def _write_root_index_note(
    target_dir: Path,
    spec_title: str,
    spec_number: str,
    slug: str,
    spec_md_content: str,
    artifacts: list[dict[str, str]],
) -> None:
    """Write the root index note for a spec.

    Creates ``<spec_title>.md`` inside ``target_dir`` with YAML
    frontmatter, a Summary section, an Artifacts section linking
    to migrated files, and References.

    Parameters
    ----------
    target_dir : Path
        The vault spec directory.
    spec_title : str
        The full spec title.
    spec_number : str
        The 3-digit spec number.
    slug : str
        The slug portion.
    spec_md_content : str
        Raw content of the original ``spec.md``.
    artifacts : list[dict[str, str]]
        List of artifact dicts with ``"filename"`` and ``"type"`` keys.
    """
    root_note = target_dir / f"{spec_title}.md"
    if root_note.exists():
        return

    created_date = parse_created_date(spec_md_content)
    today = date.today().isoformat()
    domain = assign_domain(slug)
    summary = extract_summary(spec_md_content)

    # Frontmatter
    frontmatter_lines = [
        "---",
        f"title: {spec_title}",
        "type: spec",
        "tags:",
        "  - type/spec",
        f"  - {domain}",
        "spec-refs:",
        f"  - docs/vault/Specs/{spec_title}/",
        "status: draft",
        f"created: '{created_date}'" if created_date else "created: ~",
        f"updated: '{today}'",
        "aliases:",
        f"  - {spec_title}",
        "---",
    ]

    # Body
    body_lines: list[str] = [
        "",
        f"# {spec_title}",
        "",
    ]
    if summary:
        body_lines.append("## Summary")
        body_lines.append("")
        body_lines.append(summary)
        body_lines.append("")

    # Artifacts section
    body_lines.append("## Artifacts")
    body_lines.append("")
    for art in artifacts:
        body_lines.append(f"- [[{art['filename'].removesuffix('.md')}|{art['type']}]]")
    if not artifacts:
        body_lines.append("_(No artifacts migrated.)_")
    body_lines.append("")

    # References
    body_lines.append("## References")
    body_lines.append("")
    body_lines.append("- [[Specs/Specs|Specs]]")

    target_dir.mkdir(parents=True, exist_ok=True)
    root_note.write_text(
        "\n".join(frontmatter_lines) + "\n" + "\n".join(body_lines) + "\n",
        encoding="utf-8",
    )


def _move_scaffold_dir(source: Path, destination: Path) -> None:
    """Move a scaffold subdirectory as-is (no frontmatter injection).

    Parameters
    ----------
    source : Path
        Source scaffold directory in ``specs/``.
    destination : Path
        Target directory in ``docs/vault/Specs/``.
    """
    if not source.exists():
        return
    if destination.exists():
        # Already moved; remove source if still present
        shutil.rmtree(source)
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))


def _fix_existing_files(vault_specs_dir: Path) -> None:
    """Fixup frontmatter and wikilinks in already-migrated files.

    Repairs three issues in the first migration pass:
      1. ``created: ''`` / ``updated: ''`` → ``created: ~`` / ``updated: ~``
      2. Root note wikilinks with ``.md`` suffix stripped
      3. Root notes with empty ``created: ''`` fallback

    Scans the vault Specs/ directory directly (does not rely on
    ``build_migration_plan``, whose source ``specs/`` may already be empty).

    Parameters
    ----------
    vault_specs_dir : Path
        Path to ``docs/vault/Specs/``.
    """
    if not vault_specs_dir.exists():
        return

    for spec_dir in sorted(vault_specs_dir.iterdir()):
        if not spec_dir.is_dir():
            continue

        # Fix artifact files: '' → ~ for dates
        for fpath in sorted(spec_dir.iterdir()):
            if not fpath.is_file() or not fpath.suffix == ".md":
                continue
            if fpath.stem == spec_dir.name:
                # Root note — handled separately below
                continue
            content = fpath.read_text(encoding="utf-8")
            modified = content.replace("created: ''", "created: ~").replace(
                "updated: ''", "updated: ~"
            )
            if modified != content:
                fpath.write_text(modified, encoding="utf-8")

        # Fix root note
        root_note = spec_dir / f"{spec_dir.name}.md"
        if root_note.exists():
            content = root_note.read_text(encoding="utf-8")
            modified = content.replace("created: ''", "created: ~")

            modified = re.sub(
                r"(\[\[[^]|]+)\.md(\|[^]]+\]\])",
                r"\1\2",
                modified,
            )
            if modified != content:
                root_note.write_text(modified, encoding="utf-8")


# ---------------------------------------------------------------------------
# High-level operations
# ---------------------------------------------------------------------------


def dry_run_migration(specs_dir: Path, vault_specs_dir: Path) -> list[str]:
    """Generate a human-readable dry-run plan.

    Parameters
    ----------
    specs_dir : Path
        Path to the ``specs/`` directory.
    vault_specs_dir : Path
        Path to the ``docs/vault/Specs/`` directory.

    Returns
    -------
    list[str]
        Lines of human-readable output.
    """
    plan = build_migration_plan(specs_dir, vault_specs_dir)
    lines: list[str] = [
        "Migration Plan",
        "===============",
        "",
    ]

    for entry in plan:
        title = entry["title"]
        assert isinstance(title, str)
        lines.append(f"Spec {title}")
        lines.append(f"  Source: {entry['source']}")
        lines.append(f"  Target: {entry['target_dir']}")
        lines.append(f"  Root note: {entry['root_note_path']}")

        artifacts = entry["artifacts"]
        assert isinstance(artifacts, list)
        if artifacts:
            lines.append("  Artifacts to migrate:")
            for art in artifacts:
                assert isinstance(art, dict)
                lines.append(f"    - {art['filename']} (type: {art['type']})")
        else:
            lines.append("  No artifacts to migrate.")

        scaffold_dirs = entry["scaffold_dirs"]
        assert isinstance(scaffold_dirs, list)
        if scaffold_dirs:
            lines.append("  Scaffold dirs to migrate:")
            for sd in scaffold_dirs:
                assert isinstance(sd, dict)
                from_path = sd["source"]
                assert isinstance(from_path, str)
                lines.append(f"    - {Path(from_path).name}/")

        lines.append("")

    lines.append(f"Total: {len(plan)} spec(s)")
    return lines


def verify_migration(specs_dir: Path, vault_specs_dir: Path) -> tuple[bool, list[str]]:
    """Check that all specs are represented in the vault.

    Verifies that for each spec directory under ``specs_dir``, a
    corresponding title-cased directory exists under
    ``vault_specs_dir`` with a root index note.

    Parameters
    ----------
    specs_dir : Path
        Path to the ``specs/`` directory.
    vault_specs_dir : Path
        Path to the ``docs/vault/Specs/`` directory.

    Returns
    -------
    tuple[bool, list[str]]
        ``(success, missing_titles)`` where ``success`` is ``True``
        when all specs are present, and ``missing_titles`` lists any
        spec titles not yet migrated.
    """
    plan = build_migration_plan(specs_dir, vault_specs_dir)
    missing: list[str] = []

    for entry in plan:
        title = entry["title"]
        assert isinstance(title, str)
        root_note_path = entry["root_note_path"]
        assert isinstance(root_note_path, str)
        if not Path(root_note_path).exists():
            missing.append(title)

    return len(missing) == 0, missing


def apply_migration(
    specs_dir: Path, vault_specs_dir: Path, dry_run: bool = False
) -> None:
    """Execute the full spec-to-vault migration.

    In ``dry_run`` mode, no filesystem changes are made.

    Parameters
    ----------
    specs_dir : Path
        Path to the ``specs/`` directory.
    vault_specs_dir : Path
        Path to the ``docs/vault/Specs/`` directory.
    dry_run : bool
        If ``True``, print plan and return without making changes.
    """
    if dry_run:
        lines = dry_run_migration(specs_dir, vault_specs_dir)
        for line in lines:
            print(line)
        return

    plan = build_migration_plan(specs_dir, vault_specs_dir)

    for entry in plan:
        _migrate_one_spec(entry)

    # 5. Fixup: repair frontmatter in any already-migrated files
    _fix_existing_files(vault_specs_dir)


def _migrate_one_spec(entry: dict[str, object]) -> None:
    """Migrate a single spec directory entry.

    Handles directory creation, artifact migration, root index note
    writing, and scaffold subdirectory movement for one spec.

    Parameters
    ----------
    entry : dict
        A single migration plan entry from :func:`build_migration_plan`.
    """
    title = entry["title"]
    assert isinstance(title, str)
    target_dir_str = entry["target_dir"]
    assert isinstance(target_dir_str, str)
    target_dir = Path(target_dir_str)

    # 1. Create target directory
    target_dir.mkdir(parents=True, exist_ok=True)

    # 2. Migrate artifact files (move + frontmatter)
    artifacts = entry["artifacts"]
    assert isinstance(artifacts, list)
    for art in artifacts:
        assert isinstance(art, dict)
        src_str = art["source"]
        dst_str = art["target"]
        assert isinstance(src_str, str)
        assert isinstance(dst_str, str)
        src = Path(src_str)
        dst = Path(dst_str)
        art_type = art["type"]
        assert isinstance(art_type, str)
        _migrate_artifact_file(src, dst, title, art_type)

    # 3. Write root index note
    spec_md_content = entry.get("spec_md_content", "")
    assert isinstance(spec_md_content, str)
    slug = entry["slug"]
    assert isinstance(slug, str)
    number = entry["number"]
    assert isinstance(number, str)
    _write_root_index_note(
        target_dir=target_dir,
        spec_title=title,
        spec_number=number,
        slug=slug,
        spec_md_content=spec_md_content if spec_md_content else "",
        artifacts=[
            {"filename": str(a["filename"]), "type": str(a["type"])} for a in artifacts
        ],
    )

    # 4. Move scaffold subdirectories as-is
    scaffold_dirs = entry["scaffold_dirs"]
    assert isinstance(scaffold_dirs, list)
    for sd in scaffold_dirs:
        assert isinstance(sd, dict)
        src_sd = sd["source"]
        dst_sd = sd["target"]
        assert isinstance(src_sd, str)
        assert isinstance(dst_sd, str)
        _move_scaffold_dir(
            Path(src_sd),
            Path(dst_sd),
        )


def run(
    vault_dir: str,
    specs_dir: str,
    dry_run: bool = False,
    verify_only: bool = False,
    apply: bool = False,
) -> int:
    """Entry point for the ``migrate-specs`` subcommand.

    Dispatches to the appropriate operation based on flags.
    Exactly one of ``dry_run``, ``verify_only``, or ``apply`` should be set.

    Parameters
    ----------
    vault_dir : str
        Path to the vault root (e.g. ``"docs/vault"``).
    specs_dir : str
        Path to the specs root (e.g. ``"specs"``).
    dry_run : bool
        Print migration plan without making changes.
    verify_only : bool
        Check migration completeness and exit.
    apply : bool
        Execute the migration.

    Returns
    -------
    int
        Exit code: ``0`` for success, ``1`` for failures.
    """
    vault_path = Path(vault_dir).resolve()
    vault_specs_dir = vault_path / "Specs"
    specs_path = Path(specs_dir).resolve()

    if dry_run:
        lines = dry_run_migration(specs_path, vault_specs_dir)
        for line in lines:
            print(line)
        return 0

    if verify_only:
        success, missing = verify_migration(specs_path, vault_specs_dir)
        if success:
            print("All specs are migrated.")
            return 0
        print("Missing specs:")
        for m in missing:
            print(f"  - {m}")
        return 1

    if apply:
        apply_migration(specs_path, vault_specs_dir, dry_run=False)
        print("Migration complete.")
        return 0

    return 0
