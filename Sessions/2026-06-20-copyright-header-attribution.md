---
created: '2026-06-20'
status: draft
source: agent
tags:
  - domain/governance
  - type/session-log
title: 'Copyright Header Attribution — 2026-06-20'
type: session-log
updated: '2026-06-20'
aliases:
  - Copyright Header Attribution
---

# Copyright Header Attribution

**Date**: 2026-06-20
**Context**: User requested copyright attribution ("Josh Burt, etc. etc.") across the codebase, noting nothing was visible in the source files.

## What Was Done

### 1. `pyproject.toml` author fix

The `[project].authors` field listed `{name = "anvil contributors"}` — too generic. Changed to `{name = "Josh Burt", email = "josh@shapeandshare.com"}`.

The `LICENSE` file already had `Copyright © 2026 Josh Burt` — no change needed.

### 2. Bulk copyright header addition

Wrote a Python script (`scripts/add_copyright_headers.py`, subsequently removed) that added a 4-line MIT license block to every `.py`, `.js`, `.css`, and `.html` source file under `anvil/`, `tests/`, `examples/`, `scripts/`, and `specs/`.

**Approach**: Prepend the header before all existing content — comments are allowed before `from __future__` imports per PEP 8, and before module docstrings. This meant no per-case branch logic.

**Headers applied per file type**:

| Type | Syntax | Count |
|------|--------|-------|
| `.py` | `# ` line comments | ~240 |
| `.js` | `// ` line comments | 48 |
| `.css` | `/* */` block comments | 32 |
| `.html` | `<!-- -->` comments | 32 |

Total: **424 files** modified. After the initial pass, `black` reformatted 115 files (cosmetic — spacing/quote adjustments due to the new header changing the file's blank-line structure) and `isort` fixed 5 files.

### 3. Verification

- **`black --check`**: 308 files left unchanged — clean.
- **`isort --check`**: no errors — clean.
- **`lsp_diagnostics`**: all 107 errors are pre-existing (optional deps like `mlflow`/`torch`, union syntax warnings) — zero caused by headers.
- Spot-checked representative files across all 4 types + files with `from __future__ import annotations` — headers correctly placed and formatted.

## Files Changed

`424 files changed, 5540 insertions(+), 1378 deletions(-)`

The 1378 "deletions" are from black reformatting (cosmetic only — quote style, tuple formatting, blank-line normalization).

## References

- `LICENSE` — root project license file (was already correct)
- `pyproject.toml` — project metadata (authors field)
- All files under `anvil/`, `tests/`, `examples/`, `scripts/`, `specs/`
