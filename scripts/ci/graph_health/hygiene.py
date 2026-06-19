"""Semantic hygiene analysis for vault wikilink graph.

Tag conformity vs controlled vocabulary, near-duplicate tags,
frontmatter completeness, phantom links, over-linking.
"""

import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .types import HygieneMetrics, NoteMetadata

# Controlled vocabulary constants (copied from vault_audit.py conventions)
TYPE_VOCAB: set[str] = {
    "type/principle",
    "type/design",
    "type/system",
    "type/reference",
    "type/moc",
    "type/decision",
    "type/discovery",
    "type/session-log",
}

STATUS_VOCAB: set[str] = {
    "status/draft",
    "status/wip",
    "status/reviewed",
    "status/canonical",
}

DOMAIN_VOCAB: set[str] = {
    "domain/architecture",
    "domain/core",
    "domain/training",
    "domain/inference",
    "domain/export",
    "domain/ui",
    "domain/database",
    "domain/operations",
    "domain/tooling",
    "domain/vault",
    "domain/governance",
    "domain/mcp",
    "domain/content",
}


def compute_hygiene(
    notes: dict[str, NoteMetadata],
    vault_root: Path,
    filename_index: dict[str, list[Path]] | None,
) -> HygieneMetrics:
    """Compute semantic hygiene metrics for the vault.

    Args:
        notes: Mapping from note stem to NoteMetadata.
        vault_root: Path to docs/vault/.
        filename_index: Optional pre-built index mapping wikilink stems to file paths.

    Returns:
        HygieneMetrics dataclass with all hygiene checks.
    """
    controlled_tags = _load_controlled_tags(vault_root)

    non_conformant_tags: list[tuple[str, str]] = []
    near_duplicate_tags: list[tuple[str, str]] = []
    single_use_tags: list[str] = []
    missing_fields: list[tuple[str, str]] = []
    type_mismatches: list[tuple[str, str, str]] = []
    inconsistent_dates: list[tuple[str, str]] = []
    phantom_links: list[tuple[str, str]] = []
    over_linking: list[tuple[str, str, str]] = []

    all_tags: dict[str, int] = defaultdict(int)
    tag_notes: dict[str, list[str]] = defaultdict(list)

    for stem, note in notes.items():
        for tag in note.tags:
            all_tags[tag] += 1
            tag_notes[tag].append(stem)

            if tag not in controlled_tags:
                non_conformant_tags.append((stem, tag))

    near_duplicate_tags = _find_near_duplicate_tags(list(all_tags.keys()))
    single_use_tags = [tag for tag, count in all_tags.items() if count == 1]
    unused_tags = [tag for tag in controlled_tags if tag not in all_tags]

    required_fields = ["title", "type", "tags", "created", "updated"]
    for stem, note in notes.items():
        for field in required_fields:
            if field not in note.frontmatter:
                missing_fields.append((stem, field))

        tags_value = note.frontmatter.get("tags")
        if tags_value is not None and not isinstance(tags_value, list):
            type_mismatches.append((stem, "tags", "list"))

        created = note.frontmatter.get("created")
        updated = note.frontmatter.get("updated")

        if created and not _is_valid_date(created):
            inconsistent_dates.append((stem, f"created date invalid: {created}"))
        if updated and not _is_valid_date(updated):
            inconsistent_dates.append((stem, f"updated date invalid: {updated}"))

    # Phantom links
    for stem, note in notes.items():
        for target in note.outbound_stems:
            resolved = target.rsplit("/", 1)[-1] if "/" in target else target
            if resolved not in notes:
                phantom_links.append((stem, target))

    # Over-linking
    over_linking = _find_over_linking(notes, vault_root)

    # Tag conformity percentage
    total_tags = sum(all_tags.values())
    conformant_tags = total_tags - len(non_conformant_tags)
    tag_conformity_pct = (
        (conformant_tags / total_tags * 100) if total_tags > 0 else 100.0
    )

    # Frontmatter completeness percentage
    total_notes = len(notes)
    notes_with_missing = len({stem for stem, _ in missing_fields})
    complete_notes = total_notes - notes_with_missing
    frontmatter_completeness_pct = (
        (complete_notes / total_notes * 100) if total_notes > 0 else 100.0
    )

    tag_conformity_class = _classify_percentage(tag_conformity_pct)
    frontmatter_completeness_class = _classify_percentage(
        frontmatter_completeness_pct
    )

    return HygieneMetrics(
        non_conformant_tags=non_conformant_tags,
        near_duplicate_tags=near_duplicate_tags,
        single_use_tags=single_use_tags,
        unused_tags=unused_tags,
        missing_fields=missing_fields,
        type_mismatches=type_mismatches,
        inconsistent_dates=inconsistent_dates,
        phantom_links=phantom_links,
        over_linking=over_linking,
        tag_conformity_pct=tag_conformity_pct,
        tag_conformity_class=tag_conformity_class,
        frontmatter_completeness_pct=frontmatter_completeness_pct,
        frontmatter_completeness_class=frontmatter_completeness_class,
    )


def _load_controlled_tags(vault_root: Path) -> set[str]:
    """Load controlled vocabulary tags from _meta/tags.md and constants.

    Args:
        vault_root: Path to the vault root.

    Returns:
        Set of all controlled tag strings.
    """
    tags: set[str] = set()

    tags_path = vault_root / "_meta" / "tags.md"
    if tags_path.exists():
        try:
            content = tags_path.read_text(encoding="utf-8")
        except OSError:
            pass
        else:
            lines = content.split("\n")
            in_frontmatter = False
            frontmatter_end = False

            for line in lines:
                line = line.rstrip()
                if line == "---":
                    if not in_frontmatter:
                        in_frontmatter = True
                    else:
                        frontmatter_end = True
                        in_frontmatter = False
                    continue
                if in_frontmatter or not frontmatter_end:
                    continue
                match = re.match(r"^\s*-\s+`?([a-z]+/[a-z\-]+)`?", line)
                if match:
                    tags.add(match.group(1))
                match = re.match(r"^\s*-\s+`?([a-z\-]+)`?\s+—", line)
                if match and "/" not in match.group(1):
                    tags.add(match.group(1))

    tags.update(TYPE_VOCAB)
    tags.update(STATUS_VOCAB)
    tags.update(DOMAIN_VOCAB)

    return tags


def _find_near_duplicate_tags(tags: list[str]) -> list[tuple[str, str]]:
    """Find near-duplicate tags based on case and Levenshtein distance.

    Args:
        tags: List of all tag strings used in the vault.

    Returns:
        List of (tag_a, tag_b) pairs that are near duplicates.
    """
    duplicates: list[tuple[str, str]] = []
    seen_lower: set[str] = set()

    for tag in tags:
        tag_lower = tag.lower()
        if tag_lower in seen_lower:
            for other in tags:
                if other.lower() == tag_lower and other != tag:
                    duplicates.append((other, tag))
                    break
        seen_lower.add(tag_lower)

    for i in range(len(tags)):
        for j in range(i + 1, len(tags)):
            if _levenshtein_distance(tags[i], tags[j]) <= 2:
                pair = (tags[i], tags[j])
                reverse = (tags[j], tags[i])
                if pair not in duplicates and reverse not in duplicates:
                    duplicates.append(pair)

    return duplicates


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings.

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        Edit distance (number of insertions/deletions/substitutions).
    """
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def _is_valid_date(value: Any) -> bool:
    """Check if a value is a valid date string or date object.

    Args:
        value: Value to check.

    Returns:
        True if the value is a valid date.
    """
    if isinstance(value, (date, datetime)):
        return True
    if not isinstance(value, str):
        return False
    val = value.strip().strip("'\"")
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            datetime.strptime(val, fmt)
            return True
        except ValueError:
            continue
    return False


def _find_over_linking(
    notes: dict[str, NoteMetadata], vault_root: Path
) -> list[tuple[str, str, str]]:
    """Find over-linking within sections of notes.

    Detects duplicate wikilinks in the same section of a note.

    Args:
        notes: All scanned notes.
        vault_root: Root of the vault (unused, kept for API compatibility).

    Returns:
        List of (note_stem, section, target) for over-linked targets.
    """
    over_linking: list[tuple[str, str, str]] = []
    wikilink_pattern = re.compile(r"\[\[([^\]]+)\]\]")

    for stem, note in notes.items():
        try:
            content = note.path.read_text(encoding="utf-8")
        except OSError:
            continue

        # Strip YAML frontmatter
        fm_match = re.match(r"^---\s*\n.*?\n---\s*\n", content, re.DOTALL)
        if fm_match:
            content = content[fm_match.end() :]

        sections = re.split(r"^(##+ .+)$", content, flags=re.MULTILINE)
        current_section = "root"
        section_links: dict[str, set[str]] = defaultdict(set)

        i = 0
        while i < len(sections):
            part = sections[i]
            if i % 2 == 1:
                current_section = part.strip()
                i += 1
                continue
            for match in wikilink_pattern.finditer(part):
                link = match.group(1)
                if link in section_links[current_section]:
                    over_linking.append((stem, current_section, link))
                else:
                    section_links[current_section].add(link)
            i += 1

    return over_linking


def _classify_percentage(pct: float) -> str:
    """Classify a percentage into healthy/warning/critical.

    Args:
        pct: Percentage value (0-100).

    Returns:
        Classification string.
    """
    if pct >= 100:
        return "healthy"
    elif pct >= 90:
        return "warning"
    else:
        return "critical"