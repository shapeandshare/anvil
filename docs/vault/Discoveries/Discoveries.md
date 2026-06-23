---
title: Discoveries
type: moc
tags:
  - type/moc
  - domain/vault
created: 2026-06-18T00:00:00.000Z
updated: '2026-06-21T18:00:00.000Z'
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
- [[Discoveries/canvas-particle-amplitude-vs-frequency-perceived-speed|Canvas Particle: Amplitude vs Frequency Perceived-Speed Trap]] — Raising particle wander amplitude to "meander more" made them look *faster*; the oscillation was being accumulated into position as a velocity. Fixed by modeling motion as a slow base drift plus a bounded positional sway, decoupling path width (amplitude) from speed (frequency).
- [[Discoveries/css-multi-background-position-parallax|CSS Multi-Background-Position Parallax]] — A single pseudo-element renders a multi-band parallax particle field by animating each `background-position` list entry by its own tile height in one keyframe. Also the dark-on-dark contrast trap (author soot *light*, contrast in per-dot alpha) and the unregistered-`particleConfig.type` silent fallback to CSS.
- [[Discoveries/signal-gated-decorations-invisible-at-rest|Signal-Gated Decorations Are Invisible at Rest]] — A theme that builds its primary furniture inside the session-gated `mapping()` (DOM-injected sprites/gauges) shows almost nothing at rest; only the always-on CSS tier is visible before a run. The Vinyl tape-deck reels/VU meters are session-gated by design — evaluate themes both with and without an active run.
- [[Discoveries/global-particle-speed-via-sim-step-cadence|Global Particle Speed via Sim-Step Cadence Gating]] — Slowing *all* particle effects uniformly (idle + active) can't be done by scaling the `timestamp` alone, because per-frame position integration is delta-less. The fix is a single `SPEED_SCALE` knob that gates the simulation step on accumulated wall-clock time and feeds effects a scaled `simClock`; skipped frames don't clear the canvas, so there's no flicker.
- [[Discoveries/multi-layer-radial-gradient-rain-failure|Multi-Layer Radial-Gradient Rain Effect Invisible on Pseudo-Elements]] — 40–49 `radial-gradient()` layers with soft edges on `.app-shell::before` produced no visible droplets, while the same pseudo-element renders a solid color fine. Probably a compositing limit or sub-pixel rendering issue.
- [[Discoveries/particle-effect-strict-mode-undeclared-glow|Particle Effect Strict-Mode Undeclared Variable (`glow`)]] — Strict mode in `particle-system.js` threw `ReferenceError: glow is not defined` because the `energy` effect's `var` declaration omitted `glow`, even though it was assigned and used in the render loop. Sibling effect `biolum` had it correct.

- [[Discoveries/sonarcloud-mcp-env-passthrough|SonarCloud MCP Docker Env Passthrough Bug]] — The `sonarcloud` MCP in `opencode.json` used Docker env passthrough (`-e VARNAME` without `=VALUE`), which failed because the vars weren't in the shell environment. Fixed by inlining the project constants matching `shared/sonar.mk`.
- [[Discoveries/github-token-ci-trigger-restriction|GITHUB_TOKEN CI Trigger Restriction]] — PRs opened by `GITHUB_TOKEN` do not trigger CI checks under branch protection, forcing a fine-grained PAT (`BUMP_PAT`) for auto-merge release workflows. A non-obvious GitHub platform constraint.

## Discoveries from this session
- [[Discoveries/pre-commit-and-pr-ready-tooling-pattern|Pre-commit and pr-ready Tooling Pattern]] — `make format` and `make typecheck` were documented stubs with no recipes (silent no-ops), and the CI `typecheck` gate was passing without running mypy. The `pr-ready` target and pre-commit hook close the gap between local dev and CI enforcement.

## Discoveries from this session (2026-06-22 — Modal local-mode boundary)

- **Modal is local-mode only, not a SaaS compute path**: ModalBackend is explicitly
  a local-mode cloud GPU option. The SaaS architecture (ADR-030) uses AWS Batch for
  compute. Modal lacks `job_events`, `ResourceSpec`, `EventBus` integration, IAM auth,
  checkpointing, and usage metering — all requirements for SaaS-mode compute that
  Batch provides. The boundary is documented in [[Discoveries/modal-local-mode-boundary]],
  cross-referenced in [[Decisions/ADR-015-pluggable-compute-backends|ADR-015]],
  and explicitly marked in the `DualBackend.md` reference. CLI help text and the
  training UI tooltip now say "local mode only."

## Discoveries from this session (2026-06-21 — UX rules integration)

- **UX linter FILES default silently empty without `origin/main`**: `shared/ux.mk` uses `git diff --name-only --diff-filter=ACMR origin/main...` to auto-detect changed files. If `origin/main` doesn't exist (detached HEAD, shallow clone, no remote), this silently returns empty — `make ux-lint` passes with zero files checked. Always pass `FILES=` explicitly when the remote baseline is uncertain. ([[Decisions/ADR-038-ux-rules-integration|ADR-038]])
- **Makefile PYTHON variable must be used in included mk files**: `shared/ux.mk` used bare `python`, which isn't on `PATH` in this environment — the `$(PYTHON)` variable (`.venv/bin/python3`) from `shared/python.mk` is required. Include-order matters: `python.mk` must precede `ux.mk` in the root Makefile's include list. ([[Decisions/ADR-038-ux-rules-integration|ADR-038]])
- **Pre-existing S4 violations baseline**: Running `make ux-lint` on all 35 templates for the first time surfaced 17 S4 violations (2 unaudited `|safe`, 15 `<div>` click handlers in FAQ/glossary templates). These existed before the gate and represent a remediation backlog, not new regressions. ([[Sessions/2026-06-21-ux-rules-integration-completion|session log]])

## Related MOCs

- [[Sessions/2026-06-10-implementation|Sessions]] — Full session logs
- [[Decisions/ADR-001-architecture-decisions|Decisions]] — Decisions made in response to discoveries
- [[Systems/Systems|Systems]] — System implementations
