#!/usr/bin/env python3
"""Vault Audit — mechanical integrity checker for docs/vault/.

Validates frontmatter schema against the controlled vocabulary, resolves
[[wikilinks]], detects broken relative markdown links, and drives the
graph-health analysis (connectivity, topology, hygiene, temporal decay,
health score) via the graph_health package.

Adapted for the anvil vault conventions (the type/ domain/ status/ axes
defined in docs/vault/_meta/tags.md).

Usage:
    python scripts/ci/vault_audit.py docs/vault
    python scripts/ci/vault_audit.py docs/vault --apply
    python scripts/ci/vault_audit.py docs/vault --diff
    python scripts/ci/vault_audit.py docs/vault --skip-graph-health

Exit codes:
    0 — clean or warnings only
    1 — any ERROR found
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
import urllib.parse
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install with: pip install PyYAML", file=sys.stderr)
    sys.exit(1)

# Ensure the package directory is importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Graph health analysis (optional — requires networkx).
GraphHealthRunner: type | None = None
try:
    from graph_health import GraphHealthRunner
except Exception:
    pass

# ---------------------------------------------------------------------------
# Controlled Vocabulary (mirrors docs/vault/_meta/tags.md)
# ---------------------------------------------------------------------------

TYPE_VOCAB = {
    "type/principle", "type/design", "type/system", "type/reference",
    "type/moc", "type/decision", "type/discovery", "type/session-log",
}

STATUS_VOCAB = {
    "status/draft", "status/wip", "status/reviewed", "status/canonical",
    "status/superseded",
}

DOMAIN_VOCAB = {
    "domain/architecture", "domain/core", "domain/training",
    "domain/inference", "domain/export", "domain/ui", "domain/database",
    "domain/operations", "domain/mlops", "domain/tracking",
    "domain/infrastructure", "domain/registry",
    "domain/tooling", "domain/vault",
    "domain/governance", "domain/mcp", "domain/content",
}

# All axes the script knows about — any tag prefix NOT here is unknown.
KNOWN_TAG_PREFIXES = {"type/", "status/", "domain/"}

# Agent note types (require aliases, source; decision/discovery also require code-refs).
AGENT_NOTE_TYPES = {"type/decision", "type/discovery", "type/session-log"}
GROUNDED_NOTE_TYPES = {"type/decision", "type/discovery"}

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

SEVERITY_ERROR = "ERROR"
SEVERITY_WARN = "WARN"
SEVERITY_SKIPPED = "SKIPPED"


@dataclass
class Finding:
    note_path: str
    line: int
    rule: str
    message: str
    severity: str  # ERROR, WARN, SKIPPED
    fixable: bool = False  # can be auto-fixed with --apply


@dataclass
class MechanicalReport:
    errors: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)
    skipped: list[Finding] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    def add(self, f: Finding) -> None:
        if f.severity == SEVERITY_ERROR:
            self.errors.append(f)
        elif f.severity == SEVERITY_WARN:
            self.warnings.append(f)
        else:
            self.skipped.append(f)


# ---------------------------------------------------------------------------
# Foundational utilities
# ---------------------------------------------------------------------------


def nfc(s: str) -> str:
    """Apply NFC Unicode normalization."""
    return unicodedata.normalize("NFC", s)


def _nfc_strings(obj: object) -> Any:
    """Recursively NFC-normalize all strings in a dict/list/str."""
    if isinstance(obj, str):
        return nfc(obj)
    if isinstance(obj, dict):
        return {k: _nfc_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_nfc_strings(item) for item in obj]
    return obj


def parse_frontmatter(path: Path) -> dict:
    """Parse YAML frontmatter from a Markdown file.

    Splits on '---' delimiters, loads the middle block with PyYAML.
    Returns {} on parse error with a logged warning. NFC-normalizes strings.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"WARN: Cannot read {path}: {e}", file=sys.stderr)
        return {}

    parts = content.split("---\n", 2)
    if len(parts) < 3:
        parts = content.split("---\r\n", 2)
    if len(parts) < 3:
        return {}

    try:
        data = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as e:
        print(f"WARN: YAML parse error in {path}: {e}", file=sys.stderr)
        return {}

    if not isinstance(data, dict):
        return {}

    return _nfc_strings(data)


def extract_wikilinks(text: str) -> list[str]:
    """Extract wikilink targets from text.

    Handles [[Target]] and [[Target|Display]] forms. Strips fenced and inline
    code spans first so example links inside backticks are not counted. Skips
    Obsidian attachment embeds (![[image.png]]) and shell-like captures.
    """
    _ATTACHMENT_EXTENSIONS = {
        ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
        ".pdf", ".mp3", ".mp4", ".ogg", ".wav", ".mov", ".avi",
    }
    clean_text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    clean_text = re.sub(r"`[^`\n]+`", "", clean_text)
    pattern = r"\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]"
    matches = re.findall(pattern, clean_text)
    result = []
    for m in matches:
        stripped = m.strip()
        if stripped and stripped[0] in ("!", "-", '"', "'", "$"):
            continue
        ext = Path(stripped.split("/")[-1]).suffix.lower()
        if ext in _ATTACHMENT_EXTENSIONS:
            continue
        result.append(nfc(stripped))
    return result


def write_json(path: Path, obj: dict) -> None:
    """Write a dict as deterministic JSON (sorted keys, LF line endings)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    path.write_text(content, encoding="utf-8")


def _parse_date_value(val: object) -> date | None:
    """Parse a date from frontmatter (ISO string or date object).

    Handles multiple formats: '2026-06-14', '2026-06-14T00:00:00.000Z',
    ''2026-06-14'', 2026-06-14 (as date object from PyYAML).
    """
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
            "%Y-%m-%dT%H:%M:%S%z",
        ):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
    return None


# ---------------------------------------------------------------------------
# Schema validator
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {"title", "type", "tags", "created", "updated"}


def _resolve_note_type(fm: dict) -> str:
    """Resolve the note's type tag, checking both tags[] and bare type: field.

    Some notes have `type: decision` as a bare YAML field rather than a
    `type/decision` tag. Accept both as equivalent.
    """
    tags = fm.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    type_tags = [t for t in tags if isinstance(t, str) and t.startswith("type/")]
    if len(type_tags) == 1:
        return type_tags[0]

    # Fall back to bare `type:` field
    bare_type = fm.get("type")
    if isinstance(bare_type, str) and bare_type:
        mapped = f"type/{bare_type}"
        if mapped in TYPE_VOCAB:
            return mapped

    return ""


def validate_schema(path: Path, fm: dict, note_path_str: str) -> list[Finding]:
    """Validate frontmatter against the controlled vocabulary schema."""
    findings = []

    def err(rule: str, msg: str, fixable: bool = False) -> None:
        findings.append(Finding(note_path_str, 1, rule, msg, SEVERITY_ERROR, fixable))

    def warn(rule: str, msg: str, fixable: bool = False) -> None:
        findings.append(Finding(note_path_str, 1, rule, msg, SEVERITY_WARN, fixable))

    # Missing frontmatter — warn, don't error (pre-existing notes)
    if not fm:
        warn("missing_frontmatter", "note has no frontmatter")
        return findings

    for f in REQUIRED_FIELDS:
        if f not in fm:
            err("missing_required_field", f"missing required field: {f}")

    tags = fm.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    # type/* — exactly one, in vocabulary
    type_tags = [t for t in tags if isinstance(t, str) and t.startswith("type/")]
    bare_type = fm.get("type")
    has_bare_type = isinstance(bare_type, str) and bool(bare_type)

    if len(type_tags) == 0 and not has_bare_type:
        err("missing_type_tag", "missing required type/* tag (and no bare type: field)")
    elif len(type_tags) == 0 and has_bare_type:
        # Bare type field present — check it maps to valid vocab
        mapped = f"type/{bare_type}"
        if mapped not in TYPE_VOCAB:
            err("invalid_type_tag", f"invalid bare type field: {bare_type!r} (not in controlled vocabulary)")
    elif len(type_tags) > 1:
        err("multiple_type_tags", f"multiple type/* tags: {type_tags}")
    elif type_tags[0] not in TYPE_VOCAB:
        err("invalid_type_tag", f"invalid type tag: {type_tags[0]!r} (not in controlled vocabulary)")

    note_type = _resolve_note_type(fm)

    # status/* — at most one, in vocabulary
    status_tags = [t for t in tags if isinstance(t, str) and t.startswith("status/")]
    if len(status_tags) > 1:
        err("multiple_status_tags", f"multiple status/* tags: {status_tags}")
    elif len(status_tags) == 1 and status_tags[0] not in STATUS_VOCAB:
        err("invalid_status_tag", f"invalid status tag: {status_tags[0]!r}")

    # domain/* — each must be in vocabulary
    domain_tags = [t for t in tags if isinstance(t, str) and t.startswith("domain/")]
    for dt in domain_tags:
        if dt not in DOMAIN_VOCAB:
            err("invalid_domain_tag", f"invalid domain tag: {dt!r} (not in controlled vocabulary)")

    # Unknown tag prefixes — any tag not on a known axis
    for tag in tags:
        if not isinstance(tag, str):
            continue
        if not any(tag.startswith(prefix) for prefix in KNOWN_TAG_PREFIXES):
            warn("unknown_tag_prefix",
                 f"tag {tag!r} does not belong to any known axis "
                 f"(type/|status/|domain/) — ad-hoc tags violate constitution")

    # Validate date formats
    created = fm.get("created")
    updated = fm.get("updated")
    if created is not None and not isinstance(created, (date, datetime)) and _parse_date_value(created) is None:
        warn("invalid_date_format", f"unparseable created date: {created!r}")
    if updated is not None and not isinstance(updated, (date, datetime)) and _parse_date_value(updated) is None:
        warn("invalid_date_format", f"unparseable updated date: {updated!r}")

    # Agent-note-specific checks
    if note_type in AGENT_NOTE_TYPES:
        title = fm.get("title", "")
        aliases = fm.get("aliases", [])
        if isinstance(aliases, list):
            if not aliases:
                warn("missing_aliases", "agent note missing aliases: field", fixable=True)
            elif aliases[0] != title and title:
                warn("aliases_title_mismatch",
                     f"aliases[0] ({aliases[0]!r}) != title ({title!r})", fixable=True)
        elif isinstance(aliases, str):
            if aliases != title and title:
                warn("aliases_title_mismatch",
                     f"aliases ({aliases!r}) != title ({title!r})", fixable=True)
        else:
            warn("missing_aliases", "agent note missing aliases: field", fixable=True)

        if "source" not in fm:
            warn("missing_source", "agent note missing source: field", fixable=True)

    # decision/discovery notes must be grounded in ≥1 code-refs entry
    if note_type in GROUNDED_NOTE_TYPES:
        refs = fm.get("code-refs", [])
        if not (isinstance(refs, list) and any(isinstance(r, str) and r.strip() for r in refs)):
            warn("missing_code_refs",
                 "decision/discovery note missing code-refs: (≥1 grounding path required)")

    return findings


# ---------------------------------------------------------------------------
# Filename index builder
# ---------------------------------------------------------------------------

def build_filename_index(vault_root: Path) -> dict[str, list[Path]]:
    """Build a case-insensitive NFC index keyed by both stem and vault-relative path.

    Bare links ([[ArchitectureOverview]]) resolve via stem key. Path-qualified
    links ([[Reference/ArchitectureOverview]]) resolve via path key. Duplicate
    stem entries indicate filename collisions (WARN). Excludes _meta/ and .obsidian/.
    """
    index: dict[str, list[Path]] = {}
    for md_path in sorted(vault_root.rglob("*.md")):
        parts = md_path.parts
        if any(p in ("_meta", ".obsidian") for p in parts):
            continue
        stem_key = nfc(md_path.stem).casefold()
        index.setdefault(stem_key, []).append(md_path)
        rel = md_path.relative_to(vault_root)
        path_key = nfc(str(rel.with_suffix(""))).casefold()
        if path_key != stem_key:
            index.setdefault(path_key, []).append(md_path)
    return index


# ---------------------------------------------------------------------------
# Wikilink resolver
# ---------------------------------------------------------------------------

def resolve_wikilinks(
    path: Path,
    fm: dict,
    body: str,
    index: dict[str, list[Path]],
    note_path_str: str,
) -> list[Finding]:
    """Resolve all [[wikilinks]] in body text (no related: field in anvil vault)."""
    findings = []

    all_links: list[str] = extract_wikilinks(body)

    # Also check related: field if present
    related = fm.get("related", [])
    if isinstance(related, list):
        for item in related:
            if isinstance(item, str):
                all_links.extend(extract_wikilinks(item))
    elif isinstance(related, str):
        all_links.extend(extract_wikilinks(related))

    seen: set[str] = set()
    unique_links = []
    for link in all_links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)

    for link in unique_links:
        key = link.casefold()
        matches = index.get(key, [])

        if len(matches) == 0:
            findings.append(Finding(
                note_path_str, 1, "wikilink_unresolved",
                f"unresolved wikilink: [[{link}]]",
                SEVERITY_ERROR
            ))
        elif len(matches) > 1:
            findings.append(Finding(
                note_path_str, 1, "wikilink_duplicate_target",
                f"wikilink [[{link}]] matches {len(matches)} files: "
                f"{[m.name for m in matches[:3]]}",
                SEVERITY_WARN
            ))
        else:
            real_stem = matches[0].stem
            link_stem = link.split("/")[-1]
            if nfc(real_stem) != link_stem and nfc(real_stem).casefold() == link_stem.casefold():
                findings.append(Finding(
                    note_path_str, 1, "wikilink_case_mismatch",
                    f"wikilink [[{link}]] resolves to [[{real_stem}]] "
                    f"(case mismatch — fragile on Linux)",
                    SEVERITY_WARN, fixable=True
                ))

    return findings


# ---------------------------------------------------------------------------
# Broken relative markdown link checker
# ---------------------------------------------------------------------------

_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)#\s]+?)(#[^)]*)?\)")


def check_broken_md_links(path: Path, note_path_str: str) -> list[Finding]:
    """Detect relative markdown links [text](target) whose target does not exist.

    Skips http/https/mailto URLs, absolute paths, anchor-only links, and links
    inside fenced code blocks or backtick spans.
    """
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings

    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
        if in_fence:
            continue

        for m in _MD_LINK_RE.finditer(line):
            if line[: m.start()].count("`") % 2 == 1:
                continue
            target = m.group(2)
            if target.startswith(("http", "https", "mailto", "/", "#", "\\")):
                continue
            decoded_target = urllib.parse.unquote(target.split("#", 1)[0])
            resolved = (path.parent / decoded_target).resolve()
            if not resolved.exists():
                findings.append(Finding(
                    note_path_str,
                    lineno,
                    "broken_md_link",
                    f"broken relative link: [{m.group(1)}]({target}) "
                    f"— target does not exist",
                    SEVERITY_ERROR,
                    fixable=False,
                ))
    return findings


# ---------------------------------------------------------------------------
# Main scan loop
# ---------------------------------------------------------------------------

def scan_vault(
    vault_root: Path,
    repo_root: Path,
) -> tuple[MechanicalReport, dict[str, list[Path]]]:
    """Scan the vault and return (report, filename_index).

    Excludes _meta/ and .obsidian/ from the note scan. Walks in sorted order
    for determinism.
    """
    report = MechanicalReport()
    filename_index = build_filename_index(vault_root)

    # Duplicate stem detection
    for key, paths in filename_index.items():
        if len(paths) > 1:
            for p in paths:
                note_path_str = str(p.relative_to(repo_root))
                report.add(Finding(
                    note_path_str, 1, "duplicate_filename",
                    f"duplicate filename stem '{key}': "
                    f"{[str(x.relative_to(repo_root)) for x in paths]}",
                    SEVERITY_WARN
                ))

    def should_exclude(p: Path) -> bool:
        return any(part in ("_meta", ".obsidian") for part in p.parts)

    all_notes = sorted(p for p in vault_root.rglob("*.md") if not should_exclude(p))

    notes_scanned = 0
    for note_path in all_notes:
        note_path_str = str(note_path.relative_to(repo_root))
        notes_scanned += 1

        fm = parse_frontmatter(note_path)
        try:
            content = note_path.read_text(encoding="utf-8")
        except OSError:
            continue

        parts = content.split("---\n", 2)
        body = parts[2] if len(parts) >= 3 else content

        for finding in validate_schema(note_path, fm, note_path_str):
            report.add(finding)
        for finding in resolve_wikilinks(note_path, fm, body, filename_index, note_path_str):
            report.add(finding)
        for finding in check_broken_md_links(note_path, note_path_str):
            report.add(finding)

    report.stats = {
        "notes_scanned": notes_scanned,
        "errors": len(report.errors),
        "warnings": len(report.warnings),
        "skipped": len(report.skipped),
    }

    return report, filename_index


# ---------------------------------------------------------------------------
# Report renderer
# ---------------------------------------------------------------------------


def render_report(report: MechanicalReport) -> str:
    """Render a human-readable Markdown report to stdout."""
    lines = []
    lines.append(f"Vault audit: {len(report.errors)} errors, "
                 f"{len(report.warnings)} warnings")
    lines.append("")

    if report.errors:
        lines.append("## Errors")
        for f in sorted(report.errors, key=lambda x: (x.note_path, x.rule, x.message)):
            lines.append(f"- {f.note_path}:{f.line} [{f.rule}] {f.message}")
        lines.append("")

    if report.warnings:
        lines.append("## Warnings")
        for f in sorted(report.warnings, key=lambda x: (x.note_path, x.rule, x.message)):
            lines.append(f"- {f.note_path}:{f.line} [{f.rule}] {f.message}")
        lines.append("")

    if report.skipped:
        lines.append("## Skipped")
        for f in report.skipped:
            lines.append(f"- {f.note_path}:{f.line} [{f.rule}] {f.message}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON output writer
# ---------------------------------------------------------------------------


def write_outputs(
    report: MechanicalReport,
    audit_dir: Path,
    output_override: Path | None = None,
    no_write: bool = False,
) -> None:
    """Write last_audit.json and audit_run_metadata.json."""
    if no_write and output_override is None:
        return

    def finding_to_dict(f: Finding) -> dict:
        return {
            "note_path": f.note_path,
            "line": f.line,
            "rule": f.rule,
            "message": f.message,
            "severity": f.severity,
        }

    audit_obj = {
        "errors": [
            finding_to_dict(f)
            for f in sorted(report.errors, key=lambda x: (x.note_path, x.rule, x.message))
        ],
        "warnings": [
            finding_to_dict(f)
            for f in sorted(report.warnings, key=lambda x: (x.note_path, x.rule, x.message))
        ],
        "skipped": [
            finding_to_dict(f)
            for f in sorted(report.skipped, key=lambda x: (x.note_path, x.rule, x.message))
        ],
        "stats": report.stats,
    }

    output_path = output_override if output_override else audit_dir / "last_audit.json"
    write_json(output_path, audit_obj)

    if not output_override:
        try:
            git_commit = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], text=True, timeout=5
            ).strip()
        except Exception:
            git_commit = "unknown"
        metadata = {
            "git_commit": git_commit,
            "run_timestamp": datetime.utcnow().isoformat() + "Z",
            "stats": report.stats,
        }
        write_json(audit_dir / "audit_run_metadata.json", metadata)


# ---------------------------------------------------------------------------
# Safe auto-fixes
# ---------------------------------------------------------------------------


def _read_note_parts(path: Path) -> tuple[str, dict, str]:
    content = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(path)
    parts = content.split("---\n", 2)
    body = parts[2] if len(parts) >= 3 else content
    return content, fm, body


def _write_note(path: Path, fm: dict, body: str) -> None:
    fm_str = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
    content = f"---\n{fm_str}---\n{body}"
    path.write_text(content, encoding="utf-8")


def patch_schema(
    path: Path,
    fm: dict,
    findings: list[Finding],
    filename_index: dict[str, list[Path]],
    note_path_str: str,
) -> bool:
    """Apply safe schema auto-fixes: missing aliases, missing source, case-mismatched links."""
    if not fm:
        return False

    modified = False
    _, _, body = _read_note_parts(path)
    fixable_rules = {f.rule for f in findings if f.fixable}

    if "missing_aliases" in fixable_rules or "aliases_title_mismatch" in fixable_rules:
        title = fm.get("title", "")
        if title:
            fm["aliases"] = [title]
            modified = True

    if "missing_source" in fixable_rules:
        fm["source"] = "agent"
        modified = True

    if "wikilink_case_mismatch" in fixable_rules:
        new_body = body
        for link_match in re.finditer(r"\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]", body):
            link_target = link_match.group(1).strip()
            key = nfc(link_target).casefold()
            matches = filename_index.get(key, [])
            if len(matches) == 1:
                real_stem = matches[0].stem
                if nfc(real_stem) != link_target:
                    new_body = new_body.replace(f"[[{link_target}]]", f"[[{real_stem}]]")
        if new_body != body:
            body = new_body
            modified = True

    if modified:
        _write_note(path, fm, body)

    return modified


def mark_stale(path: Path, reason: str) -> bool:
    """Add stale: true + stale_reason: + a callout to a note. Idempotent."""
    _, fm, body = _read_note_parts(path)

    if fm.get("stale") is True:
        return False

    fm["stale"] = True
    fm["stale_reason"] = reason

    callout = f"> [!warning] STALE — {reason}\n"
    body_lines = body.splitlines(keepends=True)
    insert_after = 0
    for i, line in enumerate(body_lines):
        if line.strip():
            insert_after = i + 1
            break
    body_lines.insert(insert_after, "\n")
    body_lines.insert(insert_after + 1, callout)
    _write_note(path, fm, "".join(body_lines))
    return True


def apply_tag_and_date_fixes(
    vault_root: Path,
    repo_root: Path,
    diff_mode: bool = False,
) -> dict[str, list[str]]:
    """Normalize tag casing against the controlled vocabulary and fill missing dates."""
    changes: dict[str, list[str]] = {}

    controlled_vocab = {}
    for tag in TYPE_VOCAB | STATUS_VOCAB | DOMAIN_VOCAB:
        controlled_vocab[tag.lower()] = tag

    for md_path in vault_root.rglob("*.md"):
        if md_path.name.startswith(".") or "_meta" in md_path.parts:
            continue
        try:
            content = md_path.read_text(encoding="utf-8")
        except OSError:
            continue

        parts = content.split("---\n", 2)
        if len(parts) < 3:
            continue
        frontmatter_text, body = parts[1], parts[2]

        try:
            fm = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(fm, dict):
            continue

        modified = False
        new_fm = fm.copy()

        if "tags" in new_fm and isinstance(new_fm["tags"], list):
            fixed_tags = []
            for tag in new_fm["tags"]:
                if isinstance(tag, str):
                    tl = tag.lower()
                    if tl in controlled_vocab and tag != controlled_vocab[tl]:
                        fixed_tags.append(controlled_vocab[tl])
                        modified = True
                    else:
                        fixed_tags.append(tag)
                else:
                    fixed_tags.append(tag)
            if modified:
                new_fm["tags"] = fixed_tags

        if "created" not in new_fm or not new_fm["created"]:
            new_fm["created"] = date.today().isoformat()
            modified = True
        if "updated" not in new_fm or not new_fm["updated"]:
            new_fm["updated"] = date.today().isoformat()
            modified = True

        if modified:
            new_frontmatter = yaml.dump(new_fm, default_flow_style=False,
                                        sort_keys=False, allow_unicode=True)
            new_content = f"---\n{new_frontmatter}---\n{body}"
            if not diff_mode:
                md_path.write_text(new_content, encoding="utf-8")
            path_str = str(md_path.relative_to(repo_root))
            changes.setdefault(path_str, [])
            if "tags" in fm and fm.get("tags") != new_fm.get("tags"):
                for old_tag, new_tag in zip(fm.get("tags", []), new_fm.get("tags", [])):
                    if old_tag != new_tag:
                        changes[path_str].append(f"tag casing: '{old_tag}' -> '{new_tag}'")
            if ("created" not in fm or not fm.get("created")) and "created" in new_fm:
                changes[path_str].append(f"added missing created date: {new_fm['created']}")
            if ("updated" not in fm or not fm.get("updated")) and "updated" in new_fm:
                changes[path_str].append(f"added missing updated date: {new_fm['updated']}")

    return changes


def apply_fixes(
    report: MechanicalReport,
    vault_root: Path,
    repo_root: Path,
    filename_index: dict[str, list[Path]],
) -> dict[str, list[str]]:
    """Apply all safe auto-fixes (--apply mode). Returns a summary of changes."""
    changes: dict[str, list[str]] = {}

    def record(path_str: str, action: str) -> None:
        changes.setdefault(path_str, []).append(action)

    fixable_by_path: dict[str, list[Finding]] = {}
    for f in report.errors + report.warnings:
        if f.fixable:
            fixable_by_path.setdefault(f.note_path, []).append(f)

    for note_path_str, findings in fixable_by_path.items():
        note_path = repo_root / note_path_str
        if not note_path.exists():
            continue
        fm = parse_frontmatter(note_path)
        if patch_schema(note_path, fm, findings, filename_index, note_path_str):
            record(note_path_str, "patched schema")

    for f in report.errors:
        if f.rule == "broken_code_ref":
            note_path = repo_root / f.note_path
            if note_path.exists():
                reason = f.message.replace("broken code-refs: ", "")
                if mark_stale(note_path, reason):
                    record(f.note_path, f"marked stale: {reason}")

    return changes


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def get_repo_root() -> Path:
    """Find the repository root via git."""
    try:
        result = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True, timeout=5
        )
        return Path(result.strip())
    except Exception:
        return Path.cwd()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Audit — mechanical integrity checker for docs/vault/"
    )
    parser.add_argument("vault_root", nargs="?", default="docs/vault",
                        help="Path to vault root (default: docs/vault)")
    parser.add_argument("--apply", action="store_true",
                        help="Apply safe auto-fixes in-place")
    parser.add_argument("--diff", action="store_true",
                        help="Show changes without modifying")
    parser.add_argument("--no-write", action="store_true",
                        help="Skip writing JSON output files")
    parser.add_argument("--skip-graph-health", action="store_true",
                        help="Skip graph health checks")
    parser.add_argument("--apply-link-predictions", action="store_true",
                        help="Also write graph-health predicted reciprocal links "
                             "(opt-in; these are algorithm-suggested and "
                             "unreviewed — off by default)")
    parser.add_argument("--output", type=Path, default=None,
                        help="Override output path for last_audit.json")
    args = parser.parse_args()

    repo_root = get_repo_root()
    vault_root = Path(args.vault_root)
    if not vault_root.is_absolute():
        vault_root = repo_root / vault_root

    if not vault_root.exists():
        print(f"ERROR: Vault root does not exist: {vault_root}", file=sys.stderr)
        return 1

    audit_dir = vault_root / "_meta" / "audit"

    report, filename_index = scan_vault(vault_root, repo_root)

    # Graph health analysis (optional — requires networkx)
    graph_health_report = None
    if not args.skip_graph_health and GraphHealthRunner is not None:
        try:
            runner = GraphHealthRunner(vault_root, repo_root)
            runner.set_filename_index(filename_index)
            runner.scan_all_notes()
            runner.build_graph()
            # Graph health is report-only by default. Predicted reciprocal links
            # are algorithm-suggested (unreviewed content) and are only written
            # when explicitly opted in via --apply-link-predictions.
            write_links = args.apply and args.apply_link_predictions
            graph_health_report = runner.run_all(apply=write_links, repo_root=repo_root)
            report_dir = audit_dir / "graph_health"
            _, md_path = runner.write_reports(graph_health_report, report_dir)
            print(f"\nGraph health report: {md_path}")
        except ImportError as e:
            print(f"WARN: Graph health skipped — missing dependency: {e}",
                  file=sys.stderr)
    elif not args.skip_graph_health and GraphHealthRunner is None:
        print("WARN: Graph health skipped — networkx not installed "
              "(run: make setup)", file=sys.stderr)

    if args.diff:
        # Preview pass only — never writes.
        changes = apply_fixes(report, vault_root, repo_root, filename_index)
        tag_date_changes = apply_tag_and_date_fixes(vault_root, repo_root, diff_mode=True)
        for path_str, actions in tag_date_changes.items():
            changes.setdefault(path_str, []).extend(actions)
        if changes:
            print("\nChanges that would be applied (--diff mode):")
            for path_str, actions in changes.items():
                for action in actions:
                    print(f"  {path_str}: {action}")
            print()

    elif args.apply:
        # Apply repeatedly until the vault stops changing. Some fixes cascade:
        # e.g. correcting a miscased type tag reveals agent-note checks (aliases,
        # source) that a single pass would miss. Bounded to avoid any infinite loop.
        all_changes: dict[str, list[str]] = {}
        for _ in range(5):
            changes = apply_fixes(report, vault_root, repo_root, filename_index)
            tag_date_changes = apply_tag_and_date_fixes(vault_root, repo_root, diff_mode=False)
            for path_str, actions in tag_date_changes.items():
                changes.setdefault(path_str, []).extend(actions)
            for path_str, actions in changes.items():
                all_changes.setdefault(path_str, []).extend(actions)
            report, filename_index = scan_vault(vault_root, repo_root)
            if not changes:
                break

        if all_changes:
            print(f"\nAuto-fixes applied to {len(all_changes)} file(s):")
            for path_str, actions in all_changes.items():
                for action in actions:
                    print(f"  {path_str}: {action}")
            print()

    print(render_report(report))

    if graph_health_report is not None:
        score = graph_health_report.health_score
        print(f"\n{'='*60}")
        print(f"VAULT GRAPH HEALTH SCORE: {score.overall:.1f}/100")
        print(f"{'='*60}")
        if score.breakdown:
            print("  Breakdown:")
            for key, val in sorted(score.breakdown.items()):
                print(f"    {key}: {val:.1f}")

    write_outputs(report, audit_dir, args.output, args.no_write)

    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())