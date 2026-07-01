---
title: Template fetch() Must Use window.apiFetch() for CSRF
type: discovery
status: draft
source: agent
related: []
code-refs:
  - anvil/api/templates/base.html
  - anvil/api/app.py
  - anvil/api/auth.py
  - anvil/api/templates/hf_browser.html
session: 2026-06-30-model-import-jobs-management
created: '2026-06-30'
updated: '2026-06-30'
summary: >-
  Cookie-authenticated state-changing requests must use window.apiFetch() not
  raw fetch() to include the required X-CSRF-Token header.
tags:
  - type/discovery
  - domain/ui
  - domain/architecture
aliases:
  - Template fetch() Must Use window.apiFetch() for CSRF
---
Templates that make state-changing POST/PUT/DELETE/PATCH requests through inline `<script>` blocks must use `window.apiFetch()` instead of raw `fetch()` to include the required `X-CSRF-Token` header, or the request is silently rejected with a 403 CSRF error.

Templates that directly use `fetch()` for state-changing POST requests silently fail with a 403 CSRF error, because cookie-authenticated requests must carry the `X-CSRF-Token` header — a detail easily missed when templates are developed independently.

The `base.html` template provides `window.apiFetch(url, opts)` which automatically resolves the CSRF token from `GET /v1/csrf-token` and attaches it as `X-CSRF-Token` on POST/PUT/DELETE/PATCH requests. Any new template that makes state-changing requests through inline `<script>` blocks must use `window.apiFetch()` instead of raw `fetch()`, or the request will be rejected by the auth middleware.

This was discovered when the HuggingFace model browser's import buttons silently failed with 403. The browser page renders fine (the page route is authenticated), but the JS POST to `/v1/models/import` was missing the CSRF header. The error was invisible to the user — the button just showed "import failed" — and the actual error message was swallowed by the `else` branch which didn't render the response body.

## References

- `anvil/api/templates/base.html` (lines 160-173 — `window.apiFetch` definition)
- `anvil/api/app.py` (lines 444-455 — CSRF token check in auth middleware)
- `anvil/api/auth.py` (lines 139-173 — CSRF token generation/verification)
- `anvil/api/templates/hf_browser.html` (lines 191-195 — fix: raw `fetch` replaced with `window.apiFetch`)
