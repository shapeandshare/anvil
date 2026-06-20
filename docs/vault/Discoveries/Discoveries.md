---
title: Discoveries
type: moc
tags:
  - type/moc
  - domain/vault
created: 2026-06-18T00:00:00.000Z
updated: '2026-06-19T19:00:00.000Z'
aliases:
  - Discoveries
---

# Discoveries

Non-obvious constraints, gaps, and conflicts discovered during agent sessions. Episodic memory written by agents during development. Each discovery records what was found and where the relevant code lives.

## Notes

- [[Discoveries/css-tooltip-viewport-overflow|CSS Tooltip Viewport Overflow]] — CSS-only tooltip centering overflows the viewport at screen edges; fixed via JS-measured CSS custom property nudging.
- [[Discoveries/db-path-mismatch-session-migration|DB Path Mismatch]] — `session.py` and `MigrationService` connected to different SQLite files after an env var rename was applied inconsistently.
- [[Discoveries/relative-import-mass-conversion|Relative Import Mass Conversion]] — ~200 absolute `anvil.X` imports existed inside the package, primarily as lazy imports inside function bodies; all converted to relative paths.
- [[Discoveries/mypy-strict-patterns|Mypy Strict Enforcement Patterns]] — Canonical patterns for `# type: ignore` removal, `Any` boundaries, optional imports, and `ignore_errors` override management.
- [[Discoveries/dead-experiment-model-in-migration-script|Dead `Experiment` Model Reference]] — Migration script references an ORM model whose table was dropped in migration 013; resolved with a local model definition.
- [[Discoveries/duplicated-forward-pass-in-engine|Duplicated Forward Pass in `engine.py`]] — `train()` contains a second copy of the transformer forward pass, creating a maintenance burden and drift risk.
- [[Discoveries/dataset-deletion-orphans-artifacts|Dataset Deletion Orphans File Artifacts]] — `DatasetService.delete_dataset()` never removes stored sample files from `LocalFileStore`; deleted datasets leave orphaned content on disk.
- [[Discoveries/tracking-service-swallows-audit-events|TrackingService Silently Swallows Audit Events]] — Lifecycle event logging silently catches all exceptions; events can go unrecorded without visibility.
- [[Discoveries/datasets-page-license-context-missing|Datasets Page License Dropdown Missing Template Context]] — License dropdown rendered empty because `datasets_page` handler never passed license catalog to the template context.
- [[Discoveries/playground-css-class-mismatch|Playground Example Prompt CSS Class Mismatch]] — CSS class `example-prompt` defined but HTML used `example-chip`; example chips were unstyled.
- [[Discoveries/vault-audit-index-ordering-bug|Vault Audit Index Ordering Bug]] — `VaultAuditService` built its filename index in the same loop as wikilink resolution, falsely flagging forward links to alphabetically-later notes; fixed with a two-pass approach.

## Related MOCs

- [[Sessions/2026-06-10-implementation|Sessions]] — Full session logs
- [[Decisions/ADR-001-architecture-decisions|Decisions]] — Decisions made in response to discoveries
- [[Systems/Systems|Systems]] — System implementations
