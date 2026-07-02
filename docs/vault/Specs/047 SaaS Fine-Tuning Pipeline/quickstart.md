---
title: 047 SaaS Fine-Tuning Pipeline — Quickstart
type: guide
tags:
  - type/guide
  - domain/training
status: draft
created: '2026-07-02'
updated: '2026-07-02'
---

# Quickstart: 047 SaaS Fine-Tuning Pipeline

## Overview

This feature extends the existing SaaS training pipeline (spec 032) to run PEFT fine-tunes (LoRA/QLoRA) on AWS Batch GPU. It reuses the compute routing from spec 046, the PEFT engine from spec 044, and asset governance from spec 042.

### Key Files

| File | Purpose |
|------|---------|
| `anvil/services/compute/saas_finetune_backend.py` | New SaaS FineTune backend (follows `ModalBackend` pattern) |
| `anvil/services/compute/resolve.py` | Update `_saas_configured()` from stub |
| `anvil/services/training/training.py` | Wire `ComputeBackendResult.SAAS` → `RegistryBackend.SAAS_FINETUNE` |
| `anvil/api/v1/saas_finetune.py` | New SaaS fine-tune API routes |
| `anvil/db/models/saas_finetune_job.py` | SaaS FineTune job ORM model |
| `anvil/db/models/usage_metering.py` | Usage metering record (optional standalone model) |

### Implementation Steps

1. **Create `SaasFinetuneBackend`** in `anvil/services/compute/saas_finetune_backend.py`
   - Follow `ModalBackend` submit-then-poll pattern
   - Reuse `_run_real_lora()` PEFT logic (from `LocalLoraBackend`)
   - Auto-register as `RegistryBackend.SAAS_FINETUNE`

2. **Update `_saas_configured()`** in `resolve.py` — replace `return False` with real availability check

3. **Wire `ComputeBackendResult.SAAS`** → `RegistryBackend.SAAS_FINETUNE` in `TrainingService`

4. **Add per-org concurrency gate** (FR-023c) — check in `SaasFinetuneBackend.run()` or a middleware

5. **Add SaaS fine-tune API routes** — POST `/saas/finetune/submit`, GET status, GET usage

6. **Add LakeFS asset resolution** — base model fetch + version match check at submission time

### Test Plan

| Test | What it verifies |
|------|------------------|
| `test_saas_finetune_submit` | Valid submit returns `run_id` + `adapter_id` |
| `test_saas_finetune_concurrency_limit` | 429 when limit exceeded |
| `test_saas_finetune_base_asset_missing` | 400 when base not in LakeFS |
| `test_saas_finetune_version_mismatch` | 400 on version mismatch |
| `test_saas_finetune_metrics_stream` | SSE events during run |
| `test_saas_finetune_usage_metered` | Usage record created after completion |
| `test_saas_finetune_retry_spot_interruption` | Retry count incremented on simulated interruption |
| `test_local_mode_unchanged` | NMRG — local fine-tune path unaffected |

### Definition of Done

- [ ] Over-local fine-tune submits to SaaS and returns a tracked adapter
- [ ] Per-org concurrency limit enforced (default 1)
- [ ] Base asset version mismatch detected and errored
- [ ] Usage metered per GPU-hour via `job_events`
- [ ] SSE metrics stream during run
- [ ] Spot interruption retried up to 3 times with backoff
- [ ] Local mode completely untouched (NMRG)
- [ ] `make test` passes; type checking clean