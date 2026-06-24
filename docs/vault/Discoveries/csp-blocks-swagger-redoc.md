---
aliases:
  - CSP Blocks Swagger and ReDoc
code-refs:
  - anvil/api/app.py
  - anvil/api/auth.py
created: '2026-06-23'
source: agent
status: draft
tags:
  - type/discovery
  - domain/infrastructure
  - domain/ui
title: CSP Blocks Swagger UI and ReDoc CDN Assets
type: discovery
updated: '2026-06-23'
---
# Discovery: CSP Blocks Swagger UI and ReDoc CDN Assets

## What was found

Swagger UI (`/docs`) and ReDoc (`/redoc`) are served by FastAPI automatically but were inaccessible because:

1. **Auth middleware blocked them** — `/docs`, `/redoc`, and `/openapi.json` weren't in `EXEMPT_ROUTES` or `EXEMPT_PREFIXES`. Added them so these pages are accessible without authentication.

2. **CSP blocked CDN assets** — Both pages load JS/CSS from `cdn.jsdelivr.net` and a favicon from `fastapi.tiangolo.com`. The strict `default-src 'self'` CSP blocked all external resources.

3. **CSP Level 3 nonce/unsafe-inline interaction** — The initial fix added `'unsafe-inline'` to `script-src` alongside the existing `'nonce-...'`. In CSP Level 3, when both are present, **`unsafe-inline` is ignored** in favor of the nonce. This meant inline scripts (like Swagger UI's initialization `<script>const ui = SwaggerUIBundle({...})</script>`) were still blocked.

## Resolution

Applied a **conditional CSP** in the security headers middleware:

- **Docs routes** (`/docs`, `/redoc`, `/openapi.json`): relaxed CSP with `script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net` — no nonce, allows CDN + inline scripts. Also added `worker-src 'self' blob:` for Swagger UI's Try It feature.

- **App routes**: strict nonce-based CSP preserved: `script-src 'self' 'nonce-{nonce}'`.

Added to `script-src`, `style-src`, `img-src`, `font-src`, and `connect-src` as needed for:
- `cdn.jsdelivr.net` — Swagger UI JS/CSS, ReDoc standalone JS
- `fonts.googleapis.com` / `fonts.gstatic.com` — ReDoc Google Fonts
- `fastapi.tiangolo.com` — favicon icon

## Prevention

When adding third-party resources that load external scripts/styles, the CSP must be updated to include the external origin. The conditional approach (relaxed for docs, strict for app) avoids weakening security for the application.

## References

- `anvil/api/app.py` — `security_headers_middleware` CSP logic
- `anvil/api/auth.py` — `EXEMPT_ROUTES` and `EXEMPT_PREFIXES`
