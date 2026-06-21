---
title: Discoveries
type: moc
tags:
  - type/moc
  - domain/vault
created: 2026-06-18T00:00:00.000Z
updated: '2026-06-20T19:00:00.000Z'
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
- [[Discoveries/vault-audit-forward-wikilink-resolution-bug|Vault Audit Forward Wikilink Resolution Bug]] — Mechanical audit built its filename index incrementally inside the wikilink-validation loop, producing false broken-link errors for alphabetically-later targets; fixed by pre-building the full index.
- [[Discoveries/static-css-no-cache-busting|Static CSS/JS Has No Cache-Busting]] — `base.html` links bare `/static/css/*.css` with no version query and `StaticFiles` uses default caching, so shipped CSS fixes can appear not to take effect until a hard refresh.
- [[Discoveries/transparent-items-gap-trick|Transparent Items with Gap Create See-Through Illusion]] — A flex/grid panel with opaque background can still appear transparent when children have `background: transparent` and `gap` separates them.
- [[Discoveries/version-stamping-bugs-after-ddd-restructure|Version Stamping Bugs After DDD Restructure]] — Stale test imports, skip-bump empty commit, and a hardcoded version string surfaced after the services restructure.
- [[Discoveries/release-workflow-git-identity-and-cz-commit|Release Workflow Git Identity and cz bump Commit Ownership]] — `cz bump` creates a commit, so git identity must be configured first and the bump-PR step must amend (not re-add) the commit `cz bump` already made.
- [[Discoveries/css-grid-overlay-replacement-techniques|CSS Techniques for Replacing Rigid Grid Overlays in Behavioral Themes]] — Two techniques: multi-angle gradient came for irregular organic shapes (CSS-only, no SVG) and SVG data-URI hex grid for geometric wireframes. Covers tile math, URL encoding, and edge cases.
- [[Discoveries/tab-switched-wizard-to-section-cards|Tab-Switched Wizard to Section Cards Pattern]] — Replacing tab-switched wizards with always-visible numbered `ds-flow-section` cards: template structure, step coloring convention, JS removal checklist, and why it works.

## Discoveries from this session

- **Fake-based tests mask real integration bugs**: the original 61 US1 tests used an in-memory `FakeVersionedContentStore`, which passed instantly but hid ~16 real bugs (broken wiring, empty-version accept, ambiguous ORM relationships, unnamed migration constraints, greenlet expired-object crashes, missing commits). Three-layer testing (unit/fake, real store+service e2e, HTTP API) is now standard for the content repo.
- **`asyncio.Lock` + `MissingGreenlet` pattern**: accessing ORM attributes after `commit()` expires them; sync-style lazy-load triggers `MissingGreenlet` in async contexts. Always capture plain ids/values before commit.
- **Alembic + SQLite + unnamed constraints**: SQLite batch mode requires all constraints to have a name. Forward FKs in CREATE TABLE are tolerated by SQLite — no need for `batch_alter_table`.
- **LakeFS OSS RBAC is enterprise-only**: fine-grained per-branch scoping and merge restrictions are not available in OSS LakeFS. Producer + management authz must be app-level regardless.
- **`VersionedContentStore` as a substrate boundary**: separating versioned content operations from the blob-level `FileStore` prevents bounded-context confusion and enables swapping the local pure-Python impl for a future LakeFS-backed SaaS impl without touching services/routes.

## Related MOCs

- [[Sessions/2026-06-10-implementation|Sessions]] — Full session logs
- [[Decisions/ADR-001-architecture-decisions|Decisions]] — Decisions made in response to discoveries
- [[Systems/Systems|Systems]] — System implementations
