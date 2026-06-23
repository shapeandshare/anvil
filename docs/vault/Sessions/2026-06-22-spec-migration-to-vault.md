---
title: 2026-06-22 Spec Migration to Vault
type: session-log
tags:
  - type/session-log
  - domain/vault
source: agent
created: 2026-06-22
updated: 2026-06-22
aliases:
  - 2026-06-22 Spec Migration to Vault
---

# Session: Spec Migration to Vault

## What was done

Full destructive migration of `specs/` into the vault knowledge graph, matching oldgrowth's pattern:

1. **Discovery/ folder fix**: Merged 3 notes from `Discovery/` into `Discoveries/`, deleted the duplicate folder, repointed 4 inbound wikilinks. (Prior session on `feat/specs-to-vault`.)

2. **Vault templates**: Ported 6 missing templates from oldgrowth (`code.md`, `spec-note.md`, `vision.md`, `reference.md`, `moc-concept.md`, `moc-domain.md`) adapted to anvil's frontmatter conventions. Added `type/spec`, `type/code`, `type/vision` to controlled vocabulary.

3. **Spec and Code tiers**: Created `Specs/Specs.md` and `Code/Code.md` folder MOCs, wired into `index.md` navigation and `Vault Structure.md`.

4. **Migrator module** (`anvil-vault migrate-specs`): 25 specs → `docs/vault/Specs/NNN Title/` with frontmatter injection, artifact prefixing, scaffold-as-is moves. TDD'd (53 unit tests), mypy strict.

5. **Audit port**: Added `_is_scaffold_path` and `_is_spec_subfile` exemption logic to `vault_audit.py`, `scanner.py`, and `connectivity.py` — ~200 spec artifact files absorbed with 0 new audit errors.

6. **Spec-kit rewire**: `common.sh`, `feature.json`, templates, git extension — all paths repointed from `specs/` to `docs/vault/Specs/`.

7. **Stale reference rewrite**: 23 vault notes, 5 Python docstrings, Makefile, 52 spec-internal cross-references updated from `specs/NNN-slug/` to `docs/vault/Specs/NNN Title/`.

8. **`specs/` deleted** after verification.

### Files changed

- Created: `anvil/services/vault/migrate_specs.py`, `tests/services/vault/test_migrate_specs.py` (53 tests)
- Modified: `vault_audit.py`, `scanner.py`, `connectivity.py`, `cli.py`, `_meta/tags.md`, `_meta/templates/*` (6 new templates), `.specify/common.sh`, `.specify/feature.json`, `.specify/templates/*` (2), `.specify/extensions/git/*` (3), 23 vault notes, 5 Python files, Makefile
- Deleted: `specs/` (25 dirs), `Discovery/` (empty)

## Key metrics

| Metric | Before | After |
|--------|--------|-------|
| Vault notes scanned | 248 | 460 |
| Audit errors | 10 | 10 (identical) |
| Audit warnings | 32 | 32 (identical) |
| Unit tests (vault) | 118 | 118 |
| `specs/` references | 85+ | 0 (live) |

## Related

- [[Decisions/ADR-039-specs-to-vault]]
- [[Specs/Specs]]
- [[Systems/Vault Structure]]
