---
title: ADR-013 — Training Config Footgun Guards: Multi-Layer Hyperparameter Validation
type: decision
tags: [type/decision, domain/training]
created: 2026-06-15
updated: 2026-06-15
---

# ADR-013: Training Config Footgun Guards — Multi-Layer Hyperparameter Validation

**Status**: Accepted

## Context

The training page exposes raw hyperparameters (n_embd, n_head, block_size, etc.) that users can freely edit. The autotune button produces safe values, but nothing prevented a user from manually entering invalid combinations:

- `n_head > n_embd` — head_dim becomes 0, model produces all zeros silently
- `n_embd % n_head != 0` — integer division truncates, attention dimensions are silently smaller than expected
- `head_dim % 2 != 0` — RoPE crashes on CPU (engine.py had a ValueError check) but silently produced wrong output on GPU (torch_engine.py was missing the check)
- `block_size > corpus chunk_size` — context capacity allocated but never used
- Both corpus and dataset selected — dataset silently takes priority, corpus ignored
- No data source selected — silently falls back to demo corpus

Each of these represents a violation of the pit-of-success principle ([[ADR-003-pit-of-success]]): the system should guide users toward correct configurations and catch mistakes early, not silently produce garbage or crash mid-training.

## Decision

Adopt a **three-layer validation architecture** for all training hyperparameters:

| Layer | Mechanism | Responsibility |
|-------|-----------|---------------|
| **UI** (training.html JS) | Live inline warnings, toggled on every keystroke | Preventative — user sees warning before clicking Start |
| **API** (training.py) | HTTP 422 with actionable error messages | Gate — rejects invalid configs at the REST boundary |
| **Engine** (torch_engine.py / engine.py) | ValueError at model construction | Last resort — catches anything that slips through |

### Principles

1. **Warn early, warn visibly** — inline warnings next to the offending input, not a banner at the bottom of the page.
2. **Log on every start** — all active warnings are echoed to the training output log so they're visible in the session record.
3. **Reject at the API** — the backend MUST independently validate and reject bad configs; the UI is a convenience, not a security boundary.
4. **Suggest fixes** — error messages should teach, not just reject. e.g. "Try n_head=4" when n_embd=20, n_head=6.
5. **No silent garbage** — every bad configuration must produce either a warning or an error before training begins.

### Warnings Implemented

| Condition | UI Warning | API Response | Engine Guard |
|-----------|-----------|-------------|--------------|
| `n_head > n_embd` | ✅ | HTTP 422 | — (caught by API) |
| `n_embd % n_head != 0` | ✅ | HTTP 422 with suggestion | — (caught by API) |
| `head_dim % 2 != 0` | ✅ | HTTP 422 | ✅ ValueError (both engines) |
| `block_size > corpus chunk_size` | ✅ | — (soft warning) | — |
| Both corpus + dataset selected | ✅ | — (soft warning) | — |
| No data source selected | ✅ | — (soft warning) | — |

Soft warnings (block_size, data source) are logged to the output pane but **not** rejected — they're informational rather than guaranteed-broken.

## Consequences

- **+** Users get immediate feedback on invalid configs as they type, before wasting a training run
- **+** Backend and engine layers serve as safety nets for API callers and automated scripts
- **+** Error messages teach correct usage (suggested n_head values)
- **+** Consistent with ADR-003 pit-of-success principle — extended from optional dependencies to configuration
- **−** Additional code to maintain in three places (but change is localized to validation functions)
- **−** HTTP 422 response is new — API consumers must handle it or get a failed request

## Compliance

- Any new training hyperparameter MUST be checked for invalid combinations in all three layers
- Autotune must always produce safe values (it already does)
- API validation MUST include actionable suggestions where possible