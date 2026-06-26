---
aliases:
  - 'Session: py.typed Marker'
  - py-typed-marker
created: '2026-06-19'
source: agent
status: draft
tags:
  - type/session-log
  - domain/architecture
  - domain/governance
title: 'Session: py.typed Marker (PEP 561)'
type: session-log
updated: '2026-06-19'
---
# Session: `py.typed` Marker (PEP 561)

**Date**: 2026-06-19
**Trigger**: User request: "ensure we add the typed marker to our python packages we export / create"

## What was done

### 1. Created `anvil/py.typed` marker file

Zero-byte file at `anvil/py.typed` per PEP 561. This declares that the `anvil` package
distributes inline PEP 484 type annotations, enabling type checkers (mypy, pyright,
pytype) to use them directly without stub generation.

### 2. Updated `pyproject.toml`

Added `"py.typed"` to `[tool.setuptools.package-data]` so the marker ships in the
wheel distribution:

```toml
[tool.setuptools.package-data]
anvil = [
    "py.typed",
    ...
]
```

### 3. Verified via wheel build

`uv build --wheel` confirmed via build log:
- `copying anvil/py.typed -> build/lib/anvil`
- `copying build/lib/anvil/py.typed -> build/bdist.macosx-11.0-arm64/wheel/./anvil`
- `adding 'anvil/py.typed'`

### 4. Updated AGENTS.md

Added a **Packaging Conventions** section under Architecture Rules documenting:
- The `py.typed` marker must be at `anvil/py.typed` (zero-byte)
- Must be listed in `[tool.setuptools.package-data]`
- Single top-level marker covers all subpackages
- Guidance for future sub-packages under the `anvil` namespace

## Rationale

The project ships as a pip-installable wheel (`anvil-0.1.0-py3-none-any.whl`) with
full type annotations. Without `py.typed`, type checkers treat the package as
untyped and fall back to stub generation or ignore types entirely — defeating the
purpose of the strict `mypy --strict` enforcement already in place.

## Files changed

```
Created:
  anvil/py.typed

Modified:
  pyproject.toml
  AGENTS.md
  docs/vault/Sessions/2026-06-19-py-typed-marker.md  (this file)
```

## Tags

- type/session-log
- domain/architecture
- domain/governance
- status/draft

## Related

- [[Decisions/ADR-027-type-checking-conditional-allow|ADR-027: Type Checking Conditional Allow]] — related type-checking decision
- [[Code/Code|Code]] — code architecture conventions for typing
- [[Specs/012 Pip Installable Package/012 Pip Installable Package|012 Pip Installable Package]] — packaging feature specification
