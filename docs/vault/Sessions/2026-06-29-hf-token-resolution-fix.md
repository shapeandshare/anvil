---
title: HF Token Resolution Fix + Secret Management UI
type: session-log
tags:
  - type/session-log
  - domain/training
  - domain/inference
  - spec/040
  - spec/041
  - spec/042
status: draft
source: agent
aliases: HF Token Resolution Fix
created: '2026-06-29'
updated: '2026-06-29'
related:
  - 040 External Model Registry
  - 041 HuggingFace Model Browser
  - 042 Model Asset Storage
---
# Session: HF Token Resolution Fix + Secret Management UI

**Date**: 2026-06-29
**Branch**: `fix/hf-token-resolution-secret-ui`

## Summary

Fixed a bug where the model import path (`ModelImportService`) did not resolve the HF token from the encrypted UserSecret store — it only checked the `HF_TOKEN` environment variable. Also added a secret management UI to the Config page so users can set/update/clear the HF token without using the API directly. Fixed the HF Browser search which was calling the Hub API with no token at all.

## Files Changed

### Backend — Token Resolution Fix

- **`anvil/services/model_import/model_import_service.py`** — Added optional `user_secret_service` parameter, `_resolve_token()` helper (UserSecret DB → `HF_TOKEN` env var), and passes the resolved token to `source.resolve_metadata()`. Matches the pattern already used by `ModelAssetService`.

- **`anvil/workbench.py`** — Wired `user_secret_service=self.user_secrets` into `ModelImportService` constructor so the API path resolves tokens from the DB.

- **`anvil/api/v1/hf_browser_api.py`** — Changed `HubClient()` to `HubClient(token=os.environ.get("HF_TOKEN"))`. Previously called the HF Hub API completely unauthenticated.

### Frontend — Secret Management UI

- **`anvil/api/templates/config.html`** — Added a "Secrets" section-card below the Configuration Settings with:
  - Status display (configured with `●●●●●` mask or "not configured")
  - Set/Update/Clear buttons for `hf_token`
  - Modal dialogs for setting (password input) and clearing (confirmation)
  - JS-driven via existing `window.apiFetch` pattern — no secrets in server-side template context

## Token Resolution Flow (After Fix)

```
UserSecret DB (encrypted AES-256-GCM)
  → UserSecretService.resolve_token("hf_token")
    → if found: return decrypted token
    → if not found: os.environ.get("HF_TOKEN")
      → if found: return env var value
      → if not found: return None → HF Hub 403
```

### Three code paths now covered:

| Path | Token Source |
|------|-------------|
| Model Import (`ModelImportService`) | UserSecret → `HF_TOKEN` env |
| Asset Download (`ModelAssetService`) | UserSecret → `HF_TOKEN` env |
| HF Browser Search (`HubClient`) | `HF_TOKEN` env |

## Verification

- Lint: 9.84/10 (no new warnings)
- Typecheck: Success (440 files, 0 issues)
- Tests: 27/27 passed (model_import_service, hf_source, model_assets, encryption, user_secret_repo, nmrg_040)
- Jinja template parse: OK
- Coverage: 26.75% (above 23% threshold)

## Related

- [[042 Model Asset Storage]]
- [[040 External Model Registry]]
- [[041 HuggingFace Model Browser]]
