---
aliases:
  - Stripped-vs-Line Indent Bug in TYPE_CHECKING Detection
code-refs:
  - anvil/services/vault/check_relative_imports.py
  - anvil/services/vault/check_guarded_imports.py
created: '2026-06-28'
related:
  - '[[Sessions/2026-06-28-coverage-fix-session]]'
session: 2026-06-28-coverage-fix-session
source: agent
summary: >-
  Two vault check modules used `stripped = line.strip()` to check indentation
  inside TYPE_CHECKING blocks, causing imports inside those blocks to be
  treated as module-level imports (false violations).
tags:
  - type/discovery
  - domain/vault
  - status/draft
title: Stripped-vs-Line Indent Bug in TYPE_CHECKING Detection
type: discovery
updated: '2026-06-28'
---

# Stripped-vs-Line Indent Bug in TYPE_CHECKING Detection

Two vault check modules had a latent bug that caused TYPE_CHECKING-guarded imports
to be treated as module-level (non-indented) imports, producing false violations
and broken test assertions.

## Bug pattern

Both `check_relative_imports.py` and `check_guarded_imports.py` used the same
anti-pattern to detect whether a line was inside a TYPE_CHECKING block:

```python
stripped = line.strip()
# ...
if in_type_checking:
    if stripped and not stripped.startswith((" ", "\t")):
        in_type_checking = False
```

`stripped` removes leading whitespace, so an indented line like
`    from anvil.foo import Bar` becomes `from anvil.foo import Bar` —
which the indentation check sees as non-indented, immediately exiting the
TYPE_CHECKING guard and flagging the import as a violation.

## Fix

Replace `stripped.startswith(...)` with `line.startswith(...)` so the check
operates on the original (unstripped) line:

```python
if stripped and not line.startswith((" ", "\t")):
    in_type_checking = False
```

## Secondary bug: `_in_triple_quoted` single-line docstrings

`check_relative_imports.py`'s `_in_triple_quoted()` helper toggled state on
*every* line starting with `"""` or `'''`, including single-line docstrings
like `"""Docstring with import."""` where both opening and closing delimiters
are on the same line.

**Fix**: Skip lines that both *start* and *end* with triple-quote delimiters
(length > 3), preserving the multi-line docstring state machine.

## Affected modules

- `anvil/services/vault/check_relative_imports.py` — both bugs
- `anvil/services/vault/check_guarded_imports.py` — stripped-vs-line bug only

## Impact

8 pre-existing test failures in the vault test suite were caused by these bugs.
All 8 failures resolved by the fixes above, restoring 272→343 passing vault tests.