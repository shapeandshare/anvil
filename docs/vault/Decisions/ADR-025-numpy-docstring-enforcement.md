---
title: 'ADR-010: NumPy-Style Docstring Enforcement'
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/architecture
created: '2026-06-19'
updated: '2026-06-19'
status: reviewed
aliases:
  - ADR-010
source: agent
code-refs:
  - AGENTS.md
  - pyproject.toml
---
# ADR-010: NumPy-Style Docstring Enforcement

**Date**: 2026-06-19

## Status

Reviewed — active.

## Context

The anvil codebase had inconsistent docstring coverage across its 81+ Python source files:

- **~60%** of modules had a one-liner docstring
- **~20%** of classes had a brief docstring
- **~10%** of methods/functions had any documentation
- Styles were mixed: Google-style (3 files), NumPy-style (1 file), one-liners (~15 files), and many files with zero documentation

There was no linting enforcement — ruff's `D` (pydocstyle) rules were not enabled, and no pydocstyle configuration existed.

This inconsistency made the codebase harder to navigate, especially for new contributors, and created friction during code review where docstring quality was subjective.

## Decision

1. **Standardise on NumPy-style docstrings** across the entire anvil package. Every module, package, class, method, function, and constant must use the NumPy convention with `Parameters`, `Returns`, `Raises`, and `Yields` sections where applicable.

2. **Encode the convention in `AGENTS.md`** as a permanent project policy with a documented template and entity-specific guidance.

3. **Enable ruff `D` (pydocstyle) rules** with `convention = "numpy"` in `pyproject.toml` to enforce the standard programmatically.

### Docstring Template

```python
"""Short description on one line.

Extended description with more detail about behavior, edge
cases, side effects, and usage notes. Leave a blank line
between the short and long description.

Parameters
----------
param_name : type
    Description of the parameter. Start with capital letter.
param2 : type, optional
    Description. Defaults to ``None``.

Returns
-------
type
    Description of the return value. Use ``backticks`` for
    inline code references.

Raises
------
SomeException
    Description of when/why this is raised.
"""
```

### Entity-Specific Rules

| Entity | Required sections |
|--------|-----------------|
| Module | Short description; longer description of public API if helpful |
| Class | Short description; `Parameters` in `__init__` (not class docstring) |
| Method | Short description; `Parameters`, `Returns` (if not None), `Raises` (if applicable) |
| Function | Short description; `Parameters`, `Returns`, `Raises` (if applicable) |
| Constant | Inline comment or module-level docstring section |
| Property | Short description in docstring (no Parameters needed) |

### Boundaries

- One-line docstrings are acceptable **only** for trivial properties or obvious getters.
- If a method/function returns `None` and has no side effects worth documenting, omit `Returns`.
- Use `` ``backticks`` `` for parameter names, types, and code references within prose.

## Consequences

### Positive

- Consistent documentation makes the codebase navigable by both humans and AI agents.
- Ruff `D` rules prevent docstring drift during code review and CI.
- The documented template in `AGENTS.md` gives clear guidance for all contributors.
- NumPy-style is the most widely recognised convention in the Python scientific ecosystem.

### Negative

- Initial enforcement pass touched ~81 files across 13 modules — a significant one-time effort.
- Some existing Google-style docstrings (in `tracking.py`, `memory_estimator.py`, `gpu.py`) required conversion.
- `from __future__ import annotations` (PEP 563) was found in `migration.py` — this is already forbidden per AGENTS.md rule 8; its presence does not affect docstring quality but should be addressed separately.

### Neutral

- `__init__.py` files in sub-packages follow the `__init__.py` Ownership Policy (Constitution Art. VI) — authoritative namespace levels get bare docstring-only `__init__.py` files. Those docstrings serve as the package-level documentation.
- Long-running background agent tasked with adding docstrings to `anvil/services/` (17 original files + ~15 new restructured files) was still in progress at time of writing.

## Implementation

1. Added docstring convention section to `AGENTS.md` (Principle 9) with full template and entity-specific rules.
2. Launched 9 parallel agents to add NumPy-style docstrings across all modules.
3. After agent completion, enable ruff `D` rules by adding `"D"` to `[tool.ruff.lint].select` and adding `[tool.ruff.lint.pydocstyle] convention = "numpy"`.

## Compliance

- All newly authored code MUST include NumPy-style docstrings.
- Code review MUST verify docstring compliance before merging.
- `make lint` (which will run ruff `D` rules once enabled) MUST pass.
- Type-error suppression (`# type: ignore`, `cast()`, `Any` abuse) remains forbidden — docstrings are NOT a substitute for proper type annotations.

## See Also

- [[Decisions/README|Decisions]]
