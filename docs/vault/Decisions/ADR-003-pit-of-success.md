---
title: ADR-003 — Pit of Success: Opt-In Optional Capabilities with Silent Fallback
type: decision
tags: [type/decision, domain/governance]
created: 2026-06-13
updated: 2026-06-13
---

# ADR-003: Pit of Success — Opt-In Optional Capabilities with Silent Fallback

**Status**: Accepted

## Context

The project ships with optional GPU acceleration (PyTorch) declared as an `[project.optional-dependencies] gpu` extra. Constitution Article I already mandates that GPU be an opt-in layer. However, no principle explicitly governed what happens *when a user opts in but the capability is unavailable*.

Two failure modes existed:

1. **Install gap**: `make setup` installs only `.[dev]` — no torch. Users who don't read fine print get CPU-only without understanding why.
2. **Runtime gap**: If a user toggles "use GPU" in the UI or passes `--gpu` on the CLI but torch is absent (or CUDA/MPS is unavailable), the system should silently fall back to CPU — not crash, not error, not hang.

The project's `gpu.py` and `services/training.py` already implemented graceful fallback in practice, but the constitution didn't codify the principle, making it possible for future features to violate the pattern.

## Decision

Add **Article IX — Pit of Success** to the project constitution:

> All optional capabilities MUST be opt-in at every layer (install, config, runtime). The default, do-nothing path SHALL always produce a working system. When a user opts into an enhanced capability that is unavailable, the system SHALL silently fall back to the equivalent base capability — never crash, never error, never block.

This principle applies across all future optional features, not just GPU. Examples of what it governs:

| Layer | Opt-In Mechanism | Fallback Behavior |
|-------|-----------------|-------------------|
| **Install** | `pip install -e ".[gpu]"` (or `make setup-gpu`) | CPU training works without torch installed |
| **Config** | `USE_GPU=true` env var or web UI toggle | Training runs on CPU if torch is missing or no GPU detected |
| **Runtime** | `--gpu` CLI flag or `device="cuda:0"` override | `resolve_device()` returns `"cpu"` if no accelerator found |
| **Future** | Any new optional dependency group | Must default to a zero-dep or minimal-dep working alternative |

### Existing Code That Already Conforms

- `microgpt/gpu.py:detect_gpu()` — never raises; returns `GpuInfo(available=False)` with errors list
- `microgpt/gpu.py:resolve_device()` — returns `"cpu"` when no GPU available, regardless of `use_gpu=True`
- `microgpt/services/training.py` — checks `torch_available()` before dispatching to torch engine; falls back to `core.engine.train()`
- `microgpt/core/torch_engine.py` — `_TORCH_AVAILABLE` flag with graceful `ImportError` handling; `train_torch()` raises `RuntimeError` only when explicitly called without torch (which the service layer prevents)

## Consequences

- **+** New contributors have clear guidance: every optional feature needs a working default path
- **+** Users never encounter a "GPU required" error — the system always degrades gracefully
- **+** Aligns with Python packaging convention (`extras_require` / `[project.optional-dependencies]` are opt-in by design)
- **+** Formalizes what the code already does
- **−** May hide GPU misconfiguration from users who genuinely want acceleration; mitigated by `detect_gpu()` logging GPU info to MLflow and the operations dashboard
- **−** Feature authors must design and test fallback paths, adding slight overhead

## Compliance

- Every new optional dependency group MUST have a corresponding fallback code path
- No `raise` or error response MAY be emitted solely because an optional capability's runtime dependency is absent
- Review gate: any PR introducing a new optional dependency must demonstrate the fallback path in tests
- Code review checklist item: "Does this feature have a silent fallback when its optional dependency is missing?"