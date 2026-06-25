---
title: Core Engine Files Persistently Revert Docstring Changes
type: discovery
tags:
  - type/discovery
  - domain/core
  - domain/governance
created: '2026-06-19'
updated: '2026-06-19'
status: draft
source: agent
aliases:
  - Core File Docstring Revert
  - Core Engine Docstring Revert
code-refs:
  - anvil/core/autograd.py
  - anvil/core/engine.py
  - anvil/core/tokenizer.py
  - AGENTS.md
---
# Core Engine Files Persistently Revert Docstring Changes

## Discovery

During the project-wide NumPy-style docstring enforcement (session 2026-06-19), `anvil/core/autograd.py` and `anvil/core/engine.py` exhibited a persistent revert behavior:

- Docstrings from the `core/` docstring delegation agent were applied successfully (verified by agent output stating 311 and 807 line files respectively).
- On subsequent access (read/verify step), both files were found in their **original pre-docstring state** (82 and 470 lines, no module/class/method docstrings).
- This revert occurred **three times** across three separate write attempts (first via background agent, then via replacement background agent, then via direct Edit tool operations).
- No other files in the codebase exhibited this behavior. All other modules (79+ files) retained their docstrings.

## Implication

Something in the tooling or environment is systematically reverting these two files. Possible causes:

1. **Build step or hook**: The `make setup` or similar process may regenerate these files from a template or source.
2. **Linter auto-format**: ruff or black running in fix mode might be overwriting these files.
3. **File watcher/restore**: A git hook or IDE watch task restoring files from index.
4. **Tool interaction**: Some MCP tool or background agent restoring specific files to a baseline.

The behavior is limited to `anvil/core/autograd.py` and `anvil/core/engine.py` specifically — sibling file `anvil/core/tokenizer.py` retained its docstrings.

## Recommendation

If these two files need NumPy-style docstrings, the modification should be done in a dedicated session where the revert trigger can be isolated and disabled. The docstring content is trivial (standard NumPy-style module, class, and method docstrings matching the convention in AGENTS.md).

## See Also

- [[Discoveries/Discoveries|Discoveries]]
