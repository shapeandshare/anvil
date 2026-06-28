---
title: 045 Adapter Inference Export
type: spec
tags:
  - type/spec
  - domain/training
  - domain/mlops
spec-refs:
  - docs/vault/Specs/045 Adapter Inference Export/
status: draft
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - 045 Adapter Inference Export
---

# 045 Adapter Inference Export

Track B core of the [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|Fine-Tuning Arc]]: represent a LoRA
adapter as a first-class `ComputeResult` shape, run inference by composing base + adapter, and optionally
merge + export to standalone weights. Closes the external-fine-tuning loop.

## Owned

- **FRs**: FR-020, FR-021 (+ FR-021a)
- **Decisions**: FT-AD-7

## Dependencies

- [[Specs/044 Local LoRA Fine-Tuning/044 Local LoRA Fine-Tuning|044 Local LoRA Fine-Tuning]] (produces adapters)
- `anvil/services/compute/result.py`; inference service; `anvil/services/training/export.py`

## Artifacts

- [[045 Adapter Inference Export - spec|spec]]

## References

- [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc]]
- [[Reference/FineTuningArchitectureDecisions|Fine-Tuning Architecture Decisions]]
- [[Specs/Specs|Specs]]
