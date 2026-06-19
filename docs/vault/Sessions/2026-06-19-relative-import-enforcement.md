---
title: 'Session: Relative Import Enforcement'
type: session-log
tags:
  - type/session-log
  - domain/architecture
  - domain/governance
  - status/draft
created: '2026-06-19'
updated: '2026-06-19'
aliases:
  - 'Session: Relative Import Enforcement'
  - relative-import-enforcement
source: agent
---
# Session: Relative Import Enforcement

**Date**: 2026-06-19
**Trigger**: Policy declaration — "we must never use full import paths when imports from within our namespace; internally we must always use relative paths." The AGENTS.md rule #6 mentioned relative imports implicitly, but there was no standalone ban on absolute `anvil.X` imports from within the package.

## Problem

~200 `from anvil.X import Y` / `import anvil.X` statements existed inside the `anvil/` package, violating the relative-imports-only convention. The majority were **lazy imports** (inside function bodies) rather than module-level imports — these were invisible to casual review and accumulated over time.

## What was fixed

- ~200 absolute imports converted to relative equivalents across ~58 files
- Both module-level and lazy (function-body) imports were converted
- The `anvil/` package now has **zero** `from anvil.` or `import anvil.` statements

### Files changed by directory

| Directory | Files | Conversions |
|-----------|-------|-------------|
| `anvil/cli.py` | 1 | 25 |
| `anvil/api/` | 6 | 45+ |
| `anvil/services/` | 15+ | 80+ |
| `anvil/services/compute/` | 5 | 15+ |
| `anvil/services/chunking/` | 4 | 6 |
| `anvil/db/` | 8 | 15+ |
| `anvil/supervisor/` | 2 | 3 |
| `anvil/core/` | 2 | 4 |
| `anvil/storage/` | 3 | 4 |
| `anvil/_resources/migrations/` | 2 | 8 |

### AGENTS.md updated

Rule #6 (Implicit Namespace) was split into two rules:
- **#6 — Implicit Namespace**: `__init__.py` rules only
- **#7 — Relative Imports Only**: Explicit ban on absolute `anvil.X` imports from within the package. Includes lazy imports. Notes that `tests/` and `examples/` are exempt (they're outside the package).

Subsequent rules renumbered accordingly (old #7 → #8, old #8 → #9).

## Not changed

- `tests/` and `examples/` — external to the package, valid consumers of the public API. These correctly use absolute imports (`from anvil.X import Y`).

## Key discovery

Lazy imports (inside function bodies) are the primary drift vector for absolute import violations. Two root causes:
- `config.py` is a runtime-only dep imported lazily to avoid env-not-ready errors at module load time
- Authors defaulted to familiar absolute-path style without thinking about relative equivalents during late-stage additions

## Related

- [[Discoveries/relative-import-mass-conversion|Relative Import Mass Conversion]]