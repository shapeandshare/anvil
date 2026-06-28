# Contract: Configuration Page (UI)

Per-instance configuration page (FR-010–FR-017, US2/US3). New template `anvil/api/templates/config.html` + page route `GET /v1/config-page` in `pages.py`; nav tab added to `base.html`. Mirrors the **operations.html** pattern: extends `base.html`, `section-card` layout, client-fetch + render via `innerHTML`, event-delegation for actions, `window.apiFetch` (CSRF-aware) for mutations, toast + modal components. **All styling MUST use design tokens** (`var(--accent)`, `var(--space-*)`, `var(--text-*)`) per `docs/ux-rules.md` — S4/S3 findings block.

## Page route

`GET /v1/config-page` → `templates.TemplateResponse(request, "config.html", {...})`. Page-route (auth-exempt redirect to `/login` if unauthenticated, like other pages).

## Nav

Add `<a href="/v1/config-page" class="tab-item">` to the nav in `base.html` (after Operations, before About), with a settings-gear inline SVG icon and `tab-label` "Config".

## Sections (section-card layout)

1. **Settings table** — rows grouped by `apply_class`. Each row: key, current value (editable input/select for `editable` rows), source badge (`default`/`env`/`override`), an "Edit"/"Save" action and a "Reset" action for overrides. Loaded via `fetch('/v1/config')`.
2. **Pending restart banner** — shown when `pending_restart` is non-empty: lists the pending keys and the action required ("Run `anvil-instance restart <name>` to apply"). Driven by `GET /v1/config/pending-restart`.

## Interactions

- **Edit/Save** → `PUT /v1/config/{key}` via `window.apiFetch`. On success: toast; if `mlflow_restarted` → toast "MLflow restarted"; if `pending_restart` → row shows a "pending restart" badge and the banner updates.
- **Reset** → `POST /v1/config/{key}/reset`; row reverts to env/default, source badge updates.
- **Validation errors** (`400`) → inline error on the row + toast with the specific message (e.g. "Port 8080 is in use by instance 'agent-a'"); no optimistic UI change.
- **Polling**: refresh the table + pending banner every 10s (matches operations page cadence), plus immediate refresh after each mutation.

## States

- **Loading** → spinner in the settings section.
- **Empty/all-default** → table still lists all settings (source = default); no empty-state needed since the catalog is fixed.
- **Boot-critical rows** → editable but clearly labeled "applies after restart"; saving marks pending, never claims live-applied.

## Accessibility / UX rules

Explicit `type` on all `<button>`s; labels/`aria` on inputs; focus-visible states; semantic table markup; color never the sole status signal (badge text + icon). No hardcoded colors/spacing — tokens only.
