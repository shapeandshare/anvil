---
title: "Relative Import Mass Conversion"
type: discovery
status: draft
source: agent
related:
  - '[[Discoveries/Discoveries]]'
  - '[[Sessions/2026-06-19-relative-import-enforcement]]'
code-refs:
  - anvil/
session: '2026-06-19-relative-import-enforcement'
created: '2026-06-19'
updated: '2026-06-19'
summary: 'Lazy imports inside function bodies were the primary source of absolute anvil-namespace import drift — ~200 violations existed across ~60 files.'
tags:
  - type/discovery
  - domain/architecture
  - domain/governance
  - status/draft
aliases:
  - Relative Import Mass Conversion
  - lazy-import-drift
---

The codebase had ~200 instances of `from anvil.X import Y` or `import anvil.X` inside the `anvil/` package itself, violating the convention that internal imports must use relative paths. These violations were found with grep and converted systematically.

## Root Cause: Lazy Imports Are the Silent Drift Vector

The vast majority of violations were **lazy imports** (imports inside function bodies rather than at module level). Two reasons:

1. **`anvil/config.py` is a runtime-only dep** — many modules import config lazily because it requires DB path resolution that depends on environment variables that may not be set at module import time.
2. **Circular import avoidance** — some lazy imports (`services/inference.py`, `cli.py`) were written late in the project's history and the authors defaulted to the familiar absolute-path style rather than relative paths.
3. **No audit mechanism** — there was no linter rule or review check that caught absolute internal imports.

## What was fixed

- ~200 `from anvil.X import Y` / `import anvil.X` statements converted to `from ..X import Y` / `from .X import Y` equivalents
- 58 files modified across the entire package
- Handled both module-level and lazy (function-body) imports

## Enforcement

The `AGENTS.md` behavioral principle now includes a standalone rule (#7 — Relative Imports Only) that explicitly bans absolute `anvil.` prefixed imports from within the package. This needs integration into the lint/CI pipeline (e.g., a `grep` check in CI) to prevent re-introduction.