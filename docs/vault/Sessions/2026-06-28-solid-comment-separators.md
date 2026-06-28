---
title: 'Session: Solid Comment Separators Convention'
type: session-log
tags:
  - type/session-log
  - domain/architecture
  - domain/governance
  - domain/tooling
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - 'Session: Solid Comment Separators Convention'
  - solid-comment-separators
source: agent
status: draft
---
# Session: Solid Comment Separators Convention

**Date**: 2026-06-28
**Trigger**: User reported that code comment separators were using the pattern `# ---...--` (dashes) and should use solid `#` lines instead.

## What was done

### 1. Replaced all `# ---...--` comment separators across the codebase

Used a Python script to find and replace all 78 occurrences of `# -{20,}` comment separators across 10 files:

| File | Replacements |
|------|-------------|
| `anvil/api/app.py` | 16 |
| `anvil/api/auth.py` | 10 |
| `anvil/db/migration.py` | 10 |
| `anvil/services/vault/migrate_specs.py` | 10 |
| `shared/sonar.mk` | 10 |
| `tests/browser/conftest.py` | 8 |
| `anvil/services/demo/demo_bootstrap.py` | 6 |
| `anvil/api/api_key_store.py` | 4 |
| `anvil/services/compute/modal_backend.py` | 2 |
| `tests/unit/db/test_migration.py` | 2 |

The replacement preserved indentation (comment separators inside class methods were correctly handled) and matched the original line length.

### 2. Codified Principle 15 in AGENTS.md

Added "Solid Comment Separators" as Agent Behavioral Principle 15 with:
- Mandate: section-comment separators MUST use solid `#` lines, not dashes
- Correct/incorrect code examples
- Rationale: solid `#` lines are visually unambiguous, cannot be confused with docstring section underlines (`---`, `===`) or horizontal rules
- Enforcement at merge review

### 3. Verified

- Zero remaining occurrences of the old `# ---...--` pattern
- All 10 affected files read correctly with the new convention

## Key insight

The dash-based separator pattern `# ---...--` is ambiguous with reStructuredText/NumPy-style docstring section underlines (`Parameters\n----------`). Using solid `#` lines eliminates this visual confusion entirely.

## Files changed
```
Modified:
  AGENTS.md                                    # Principle 15: Solid Comment Separators
  anvil/api/app.py                             # Comment separator migration
  anvil/api/auth.py                            # Comment separator migration
  anvil/api/api_key_store.py                   # Comment separator migration
  anvil/db/migration.py                        # Comment separator migration
  anvil/services/compute/modal_backend.py      # Comment separator migration
  anvil/services/demo/demo_bootstrap.py        # Comment separator migration
  anvil/services/vault/migrate_specs.py         # Comment separator migration
  shared/sonar.mk                              # Comment separator migration
  tests/browser/conftest.py                    # Comment separator migration
  tests/unit/db/test_migration.py              # Comment separator migration

Vault:
  docs/vault/Sessions/2026-06-28-solid-comment-separators.md
```

## Tags
- type/session-log
- domain/architecture
- domain/governance
- domain/tooling
- status/draft

## Related

- [[Governance/Constitution|Constitution]] — project governance and conventions
- AGENTS.md — Principle 15: Solid Comment Separators
