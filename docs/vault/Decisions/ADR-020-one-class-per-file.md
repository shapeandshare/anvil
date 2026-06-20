---
title: 'ADR-020: One Class Per File'
type: decision
tags:
  - type/decision
  - domain/architecture
  - domain/governance
created: '2026-06-19T00:00:00.000Z'
updated: '2026-06-19T00:00:00.000Z'
aliases:
  - One Class Per File
source: agent
code-refs:
  - AGENTS.md
  - .specify/memory/constitution.md
  - anvil/services/training/export.py
---
# ADR-020: One Class Per File

## Status

accepted

## Context

The codebase had no structural rule limiting the number of classes per file, leading to files like `api/v1/datasets.py` (8 classes) and `services/inference.py` (3 classes). Multi-class files create discoverability friction — a developer must scan the entire file to understand its contents, and diffs become harder to review when unrelated classes change in the same file.

The existing `AGENTS.md` Architecture Rules already stated *"One class per file. Classes for all logic (no loose functions)"*, but there was no enforcement mechanism and the rule was not represented in the project constitution (`.specify/memory/constitution.md`). This left the rule aspirational rather than binding.

## Decision

- **One class per file** — Every Python source file MUST contain exactly one class definition.
- Permitted exceptions: utility constants, functions, enums, and module-level helpers may share a file with the primary class when they are inseparable from that class's interface.
- Exception/error classes that are tightly coupled to a primary class may share a file (e.g., `SafetensorsExportError` in the same file as `SafetensorsExportService`).
- Enforcement at merge review — any reintroduced multi-class file without explicit exception approval is reject-worthy.

All existing multi-class files are being refactored to comply in a single session (this ADR's companion refactoring pass).

## Consequences

**Easier:**
- Discoverability — each file's purpose is obvious from its name
- Diffs — class-level changes don't intermix in review
- Merge conflicts — reduced surface area for conflicting changes

**Harder:**
- More files — 21 multi-class files become ~60 single-class files
- Navigation — increased file count in directories
- Import churn — each extraction requires updating all callers

## Compliance

- `make lint` and `make typecheck` must pass after the refactoring
- A grep for `^class ` in `anvil/` should show one class per file (modulo permitted exceptions)
- Merge review gate: any new multi-class file flagged for rejection
