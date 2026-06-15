# Implementation Plan: Llama Engine Evolution & Safetensors Export

**Branch**: `006-llama-engine-evolution` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-llama-engine-evolution/spec.md`

## Summary

Evolve the anvil core training engine from GPT-2 architecture (ReLU MLP, learned position embeddings) to Llama-compatible architecture (SwiGLU, RoPE, learned RMSNorm weights). Safetensors replaces native JSON as the primary model delivery artifact — automatically generated, stored, tracked, and versioned on every training completion. Walkthrough scripts updated to teach the modern decoder-only transformer progression.

## Technical Context

**Language/Version**: Python 3.11+ (stdlib for core engine, async for web layer)  
**Primary Dependencies**: 
  - Core engine (`anvil/core/`): stdlib only (zero deps per Constitution Article I)
  - Services (`anvil/services/`): FastAPI, aiofiles, MLflow 3.x
  - Safetensors export: `safetensors>=0.4` (service layer, NOT core)
**Storage**: Local filesystem (`data/models/`) for model artifacts; SQLite via async SQLAlchemy for metadata  
**Testing**: pytest with 100% coverage (Constitution Article IV)  
**Target Platform**: macOS (MPS), Linux (CPU/CUDA)  
**Project Type**: Web service (FastAPI) + Python library (core engine)  
**Performance Goals**: SC-001 — n_embd=16, n_layer=1, n_head=4 training on 1000-char corpus under 60s  
**Constraints**: 
  - Core engine MUST remain stdlib-only
  - Export MUST be zero-synthesis — every tensor maps to a trained parameter (FR-009)
  - Loading old-format model.json MUST fail gracefully with clear error (FR-011)
**Scale/Scope**: Single-user educational training platform; models sized n_embd 16–768, n_layer 1–12

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Status | Notes |
|---------|--------|-------|
| I — Zero-Dependency Core | ✅ PASS | Core changes stay stdlib-only. Safetensors dep in service layer only |
| II — Educational Clarity | ✅ PASS | Walkthroughs updated to teach Llama architecture progression |
| III — Seeded Reproducibility | ✅ PASS | Seed=42 preserved; all new architecture components use seeded random init |
| IV — TDD Mandatory | ✅ PASS | All changes test-covered per spec acceptance scenarios |
| V — Async-First | ✅ PASS | Core remains sync exception; services async |
| VI — Implicit Namespace | ✅ PASS | No new __init__.py for internal wiring |
| VII — Layered Architecture | ✅ PASS | Changes flow through existing GPT class → Service → God Class |
| VIII — Whimsy Without Compromise | ✅ PASS | UI widgets updated for RoPE/SwiGLU visualization |
| IX — Pit of Success | ✅ PASS | Safetensors failure doesn't crash training (FR-016); graceful fallback |

**No violations.** All gates pass.

## Project Structure

### Documentation (this feature)

```text
specs/006-llama-engine-evolution/
├── plan.md              # This file (/speckit.plan command output)
├── spec.md              # Feature specification
├── research.md          # Phase 0 output — resolved unknowns
├── data-model.md        # Phase 1 output — entity definitions
├── quickstart.md        # Phase 1 output — quick start guide
├── contracts/           # Phase 1 output — interface contracts
│   ├── safetensors-export.md
│   ├── config-schema.md
│   └── walkthrough-progression.md
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
anvil/
├── core/
│   ├── __init__.py      # Updated exports
│   ├── autograd.py      # Unchanged (Value class)
│   ├── engine.py        # ★ GPT → Llama: SwiGLU, RoPE, RMSNorm weights, remove wpe/fc1/fc2
│   ├── tokenizer.py     # Unchanged
│   └── torch_engine.py  # Updated parallel Llama support
├── services/
│   ├── inference.py     # ★ Updated for new state dict keys, RoPE traces
│   ├── tracking.py      # ★ New safetensors artifact tracking
│   └── training.py      # ★ Updated for new state dict on save
├── api/
│   └── v1/
│       └── inference.py # ★ Updated widget endpoints for RoPE/SwiGLU
├── db/
│   └── models/
│       └── training_config.py  # Unchanged (arch-agnostic hyperparams)

examples/
├── train0.py → train0.py  # ★ Single neuron (unchanged concept)
├── train1.py → train1.py  # ★ Linear layer (unchanged concept)
├── train2.py → train2.py  # ★ RMSNorm with learned weights
├── train3.py → train3.py  # ★ Self-attention with RoPE
├── train4.py → train4.py  # ★ Transformer block with SwiGLU
├── train5.py → train5.py  # ★ Full Llama-aligned GPT

tests/
├── unit/
│   └── core/
│       └── test_engine.py     # ★ Updated for Llama state dict, architecture tests
├── integration/
│   └── test_training.py       # ★ Updated for new export flow
└── e2e/
    └── test_inference_widgets.py  # ★ Updated widget tests

data/models/
├── demo/
│   └── model.json         # ★ Auto-retrains with new architecture (FR-012)
└── <run_id>/
    ├── model.json          # ★ Secondary/internal representation (new state dict)
    ├── model.safetensors   # ★ Primary export artifact (FR-006)
    ├── config.json         # ★ Llama-compatible config
    └── tokenizer.json      # ★ Character-level tokenizer config
```

**Structure Decision**: Existing anvil project structure preserved. Core engine updated in-place (not a separate engine). New safetensors export in service layer. Walkthroughs updated in-place.

## Complexity Tracking

No Constitution violations to justify.

---

## Phase 0 & 1 Complete

**Phase 0 output**: [research.md](./research.md) — All 5 unknowns resolved  
**Phase 1 output**: [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)  
**Agent context**: Updated in AGENTS.md  
**Constitution re-check**: ✅ All gates still pass (no violations introduced by design)