---
title: Training Output Actions Restructure
type: session-log
tags:
  - type/session-log
  - domain/ui
  - domain/architecture
created: '2026-06-30'
updated: '2026-06-30'
status: draft
source: agent
aliases: Training Output Actions Restructure
---
# Training Output Actions Restructure

**Session**: Restructured the training page output block so action buttons and info are visible even when the raw output logs are collapsed. Removed a redundant "register model" button since auto-registration already handles it on training completion.

## What was done

### Output actions moved outside collapsible (`training.html`)
- Moved `#output-actions` div out of `#output-body` (the collapsible section) to sit between the header and the collapsible body
- Experiment info text ("Experiment #X — loss Y.ZZZZ"), "view all experiments →" link, and "mlflow →" link are now always visible
- Only the raw `<pre class="loss-display">` output logs remain collapsible

### CSS adjustment (`archetypes.css`)
- Changed `.output-actions` from `border-top` to `border-bottom` so the separator line runs between the actions and the collapsible body below

### Removed redundant "register model" button
- Discovered that `on_complete` in `api/v1/training.py` (lines 878-908) already auto-registers the model via `tracking_svc.register_source_model()` on every successful training completion
- The manual "register model" button in the UI prompted for a name/description but the API endpoint (`POST /v1/registry/models`) only accepts `experiment_id` — the name/description were silently discarded
- Removed the button from `refreshOutputActions()` and deleted the dead `openRegisterModal()` handler

## Files changed
- `anvil/api/templates/archetypes/training.html` — moved `#output-actions`, removed button + dead code
- `anvil/api/static/css/archetypes.css` — `.output-actions` border-top → border-bottom

## Related
- Auto-registration path: `api/v1/training.py` → `on_complete()` → `tracking_svc.register_source_model()`
- Manual endpoint: `POST /v1/registry/models` → same `register_source_model()` call
