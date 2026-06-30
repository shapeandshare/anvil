# Implementation Plan: Text Input Theme Consistency

**Branch**: `060-text-input-theme-consistency` | **Date**: 2026-06-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `docs/vault/Specs/060 Text Input Theme Consistency/spec.md`

## Summary

Unify the visual styling of all text-editing inputs (`<input>`, `<select>`, `<textarea>`) across the anvil web UI. Currently inputs use 4 different CSS classes (`form-input`, `widget-input`, `input`, `login-card__input`) plus bare unstyled elements in the training form and an inline-styled `<select>` in the compute backend selector. The fix is a pure CSS refactor: consolidate all inputs under a single `.form-input` component class, add a visible border (resolved from `--separator` token), fix the border-radius from 13px to 8px (per DESIGN.md), ensure theme-token inheritance, and add `:focus-visible` focus ring support. No new dependencies, no backend changes, no database migrations.

## Technical Context

**Language/Version**: CSS3 (Custom Properties), HTML5, JavaScript (minor template edits)  
**Primary Dependencies**: None new — reuses existing design tokens (`--surface-2`, `--separator`, `--accent`, `--radius-sm`, `--text`, `--text-tertiary`)  
**Storage**: N/A  
**Testing**: Visual audit + `make ux-lint` (S4 gate)  
**Target Platform**: Web (desktop + mobile browsers, iOS PWA)  
**Project Type**: Web application (FastAPI + Jinja2 + static CSS)  
**Performance Goals**: N/A — CSS-only change, zero runtime performance impact  
**Constraints**: Must comply with DESIGN.md (iOS input radius = 8px), ux-rules.md (S4/S3 hard gate), existing design token system  
**Scale/Scope**: 8 template files, 3 base CSS files, 23 theme CSS files, 1 login CSS file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity First gate (Article XI — hard MUST)**: Confirm this plan favors the simplest, most boring solution that meets the requirement:

- [x] **Simplest viable** (§11.1) — Pure CSS class consolidation. No new dependencies, no JS framework, no build tooling. The simplest fix for inconsistent inputs.
- [x] **Boring over novel** (§11.2) — Existing CSS custom properties + existing `.form-input` class reused. No novel patterns introduced.
- [x] **YAGNI** (§11.3) — No speculative abstraction (no input component plugin system, no JS component framework). Just CSS class unification.
- [x] **Reuse first** (§11.4) — Reuses existing `.form-input` as the single target class. Reuses existing token system. No new parallel styling approach.
- [x] **Testable** (§11.6) — Visual regression via Playwright screenshots (`make test-browser`). Mechanical verification via `make ux-lint` (S4 gate). Both are existing CI pipelines.

> No deviations. Complexity Tracking table is empty — no justification needed.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/060 Text Input Theme Consistency/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # (skipped — no external interfaces)
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
anvil/api/static/css/
├── tokens.css               # Add --border-input token (if needed)
├── components.css            # PRIMARY: unify .form-input, .terminal-input, etc.
├── archetypes.css            # Adapt .param-block input to use .form-input
└── login.css                 # Migrate .login-card__input to .form-input

anvil/api/templates/
├── config.html               # Fix class="input" → class="form-input"
├── login.html                # Fix .login-card__input → .form-input
├── datasets.html             # Already uses .form-input (verify)
├── hf_browser.html           # Already uses .form-input (verify)
├── dataset_curation.html     # Already uses .form-input (verify)
├── archetypes/
│   ├── training.html         # Add .form-input to 7 bare <input> elements
│   ├── playground.html       # Already uses .form-input (verify)
│   └── content_library.html  # Already uses .form-input (verify)
└── partials/
    └── concept-widgets/
        └── tokenization.html  # Migrate .widget-input → .form-input (or alias)

anvil/api/static/css/themes/  # Verify theme token coverage (likely no changes needed)
```

**Structure Decision**: Single project — all assets are existing files within the anvil package. No new files created outside the spec documentation.

## Complexity Tracking

> No violations — plan is the simplest viable approach.
