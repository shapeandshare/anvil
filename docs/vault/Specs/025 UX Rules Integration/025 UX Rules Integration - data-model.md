---
title: 025 UX Rules Integration - data-model
type: data-model
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/025 UX Rules Integration/
related:
  - '[[025 UX Rules Integration]]'
created: ~
updated: ~
---
# Data Model: UX Rules Integration

This feature has no runtime data model — it places static configuration/script artifacts. The following entities define each artifact's role and relationships.

## Entities

### UX Ruleset

| Attribute | Value |
|-----------|-------|
| **Path** | `docs/ux-rules.md` |
| **Type** | Markdown document |
| **Purpose** | Single source of truth for all UX rules |
| **Consumed by** | `ux_review.py` (via `DEFAULT_RULES`), `ux-generate` skill (agent reads ruleset), `ux-review` skill (agent reads ruleset), humans |
| **Not consumed by** | `ux_lint.py` (carries its own regex checks) |
| **State** | Read-only; edited manually when rules change |

### OpenCode Skill — ux-review

| Attribute | Value |
|-----------|-------|
| **Path** | `.opencode/skills/ux-review/SKILL.md` |
| **Type** | YAML frontmatter + Markdown (OpenCode skill format) |
| **Purpose** | Audit UI code against full ruleset; emit severity-tagged findings |
| **Reads** | `docs/ux-rules.md` (ruleset), target files (user-supplied) |
| **Mode** | Read-only; does not modify files |

### OpenCode Skill — ux-generate

| Attribute | Value |
|-----------|-------|
| **Path** | `.opencode/skills/ux-generate/SKILL.md` |
| **Type** | YAML frontmatter + Markdown (OpenCode skill format) |
| **Purpose** | Guide builder agents to produce UI code compliant with the ruleset |
| **Reads** | `docs/ux-rules.md` (ruleset) |
| **Mode** | Generative; influences agent output |

### Linter

| Attribute | Value |
|-----------|-------|
| **Path** | `scripts/ci/ux_lint.py` |
| **Type** | Python 3 script (stdlib only) |
| **Purpose** | Deterministic mechanical S4 gate |
| **Dependencies** | None (stdlib: re, os, sys) |
| **Supports** | Suppression annotations (`ux-lint:allow`, `ux-lint:allow-next`) |
| **Exit codes** | 0 = clean, 1 = unsuppressed S4 found, 2 = usage error |

### AI Review Script

| Attribute | Value |
|-----------|-------|
| **Path** | `scripts/ci/ux_review.py` |
| **Type** | Python 3 script (stdlib + urllib) |
| **Purpose** | Optional full-ruleset AI review |
| **Dependencies** | Stdlib only (urllib, json, os, re, sys) |
| **Reads** | `docs/ux-rules.md` (via `DEFAULT_RULES` or `UX_RULES` env var) |
| **Env vars** | `UX_API_KEY` (required), `UX_MODEL_BASE_URL`, `UX_MODEL`, `UX_RULES`, `UX_GATE` |
| **Exit codes** | 0 = clean, 1 = findings at/above gate severity, 2 = configuration error |

### UI Compliance Constitution Principle

| Attribute | Value |
|-----------|-------|
| **Location** | `.specify/memory/constitution.md` |
| **Type** | MUST-level constitutional principle |
| **Purpose** | Gate specs/plans/tasks via `/speckit.analyze` |
| **References** | `docs/ux-rules.md` |

### Makefile Include

| Attribute | Value |
|-----------|-------|
| **Path** | `shared/ux.mk` |
| **Type** | GNU Make include file |
| **Purpose** | Expose `ux-lint` and `ux-review` targets |
| **Reads** | `scripts/ci/ux_lint.py`, `scripts/ci/ux_review.py` |
| **Invoked by** | `include shared/ux.mk` in root `Makefile` |

## Relationships

```
docs/ux-rules.md
  ├── read by → ux-review (skill)
  ├── read by → ux-generate (skill)
  ├── read by → ux_review.py (script via DEFAULT_RULES)
  └── referenced by → constitution principle

.opencode/skills/ux-review/SKILL.md  ← agent route for deep review
.opencode/skills/ux-generate/SKILL.md  ← agent route for compliant generation

scripts/ci/ux_lint.py  ← called by make ux-lint (shared/ux.mk)
scripts/ci/ux_review.py  ← called by make ux-review (shared/ux.mk)
```

## Validation Rules

1. `docs/ux-rules.md` MUST exist and be readable for `ux_review.py` to function.
2. `ux_lint.py` MUST be invocable standalone (`python scripts/ci/ux_lint.py <file>`) or via Make.
3. `ux_review.py` MUST exit with code 2 if `UX_API_KEY` is unset.
4. Both SKILL.md files MUST have YAML frontmatter with `name` and `description` fields.
5. The constitution principle MUST use MUST-level language and reference `docs/ux-rules.md`.