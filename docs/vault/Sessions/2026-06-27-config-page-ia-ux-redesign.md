---
title: 'Session: Config page IA/UX redesign + config learning lesson'
type: session-log
tags:
  - type/session-log
  - domain/ui
  - domain/operations
  - domain/content
created: '2026-06-27'
updated: '2026-06-27'
status: draft
source: agent
aliases:
  - config-page-ia-ux-redesign
---

# Config Page IA/UX Redesign + Runtime Config Learning Lesson

**Session**: Redesigned the config page from a flat table dump to grouped informational sections with inline help, and added a dedicated runtime-config lesson to the learning arc.

## What was done

### Part A — API extension (expose catalog metadata)

The `ConfigSetting` model and `ConfigSettingOut` API schema were both missing `display_name`, `description`, `env_var`, and `default_value` — even though `CatalogEntry` (the source of truth for every setting) already had these fields. Extended both models and all four route handlers (`list_config`, `get_config`, `update_config`, `reset_config`, `list_pending_restart`) to pass them through.

**Files**: `anvil/services/runtime_config/config_setting.py`, `anvil/services/runtime_config/runtime_config_service.py`, `anvil/api/v1/schemas.py`, `anvil/api/v1/config.py`

### Part B — Config page redesign

Rewrote `anvil/api/templates/config.html` from a flat table to three grouped sections by apply class:
- **Live Settings** (green) — immediate effect, no restart
- **Sidecar Settings** (orange) — MLflow auto-restart
- **Boot-Critical Settings** (red) — pending restart required

Each setting renders as a card with: display name (with raw key as secondary), inline description, metadata grid (value, default, env var, source badge, apply class badge), and Edit/Reset actions.

Added:
- CTA banner linking to `/v1/learn/runtime-config`
- `related-lessons.html` partial (config page was the only page missing this)
- Section-level help boxes explaining each apply class

### Part C — Runtime configuration learning lesson

Added `RUNTIME_CONFIG_STEPS` (8 steps covering resolution chain, apply classes, per-setting deep dives, env var reference, troubleshooting) and a new route `GET /v1/learn/runtime-config` using the existing `concept.html` carousel template.

Added to `LEARNING_ARC` and `LEARNING_ARC_ADDITIONAL` so it appears on the Learn hub. Connected via `related_lessons` from the config page.

## Discovery

- **API gap**: `ConfigSettingOut` was returning only `key`/`value`/`source`/`apply_class` even though the `CatalogEntry` data model had `display_name`, `description`, `env_var`, and `default_value`. The UI had to show raw internal keys with no context. This was a data-through-API gap, not a missing data problem.