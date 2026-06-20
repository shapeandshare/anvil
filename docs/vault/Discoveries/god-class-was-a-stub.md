---
title: AnvilWorkbench God Class Was a Stub
type: discovery
status: draft
source: agent
related:
  - '[[Decisions/ADR-028-ci-merge-gate-enforcement]]'
code-refs:
  - anvil/cli.py
  - anvil/workbench.py
session: 2026-06-19-dx-harness-hardening
created: '2026-06-19'
updated: '2026-06-19'
summary: >-
  The AnvilWorkbench god class mandated by the constitution was never
  instantiated anywhere — a stub exposing only TrainingService. The DX hardening
  feature created a proper workbench.
tags:
  - type/discovery
  - domain/architecture
  - status/draft
---
# AnvilWorkbench God Class Was a Stub

The constitution's Article VII mandates "All services MUST be exposed through a single God Class (`AnvilWorkbench`). Routes, CLI, and tests call the God Class." During the DX hardening review, investigation revealed that `AnvilWorkbench` was defined in `anvil/cli.py` but **never instantiated anywhere in the codebase** — not by CLI functions, not by route handlers, not by tests. It was a stub exposing only `TrainingService`.

Routes and CLI functions directly instantiated services (`TrackingService()`, `CorpusService()`, `DatasetService()` etc.), bypassing the god class entirely. This means Article VII was violated repo-wide — the architectural layer it describes didn't match reality.

## Why This Happened

The god class was introduced early in the project but never wired into consumers. Services were added in a flat service layer (`anvil/services/`) and route modules imported them directly as needed. The god class was never migrated to track the growing service catalog.

## Resolution

The DX hardening feature created `anvil/workbench.py` with a fully-populated `AnvilWorkbench` exposing `TrainingService`, `TrackingService`, `InferenceService`, and `SafetensorsExportService` as lazy properties. Consumer migration is in progress (FR-018) — some routes still instantiate services directly (notably session-dependent services like `DatasetService(repo)`).

## Lesson

Architecture rules declared in governance must be verified against actual code patterns. A "declared-only" rule trains agents and contributors to treat governance as aspirational rather than binding.

## References

- `anvil/cli.py` — original god class location (stub)
- `anvil/workbench.py` — new god class with all services
- [[Decisions/ADR-028-ci-merge-gate-enforcement]]
