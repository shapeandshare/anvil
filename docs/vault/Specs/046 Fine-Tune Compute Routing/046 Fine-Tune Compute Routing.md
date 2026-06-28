---
title: 046 Fine-Tune Compute Routing
type: spec
tags:
  - type/spec
  - domain/training
  - domain/operations
spec-refs:
  - docs/vault/Specs/046 Fine-Tune Compute Routing/
status: draft
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - 046 Fine-Tune Compute Routing
---

# 046 Fine-Tune Compute Routing

Offload track of the [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|Fine-Tuning Arc]]: a fine-tune is a
first-class compute job; `resolve.py` routes local vs SaaS by computed `ResourceSpec` under D4, and
adapter-bearing results normalize identically across backends.

## Owned

- **FRs**: FR-022 (+ FR-022a, FR-022b)
- **Decisions**: FT-AD-6 (references AD-1)

## Dependencies

- [[Specs/044 Local LoRA Fine-Tuning/044 Local LoRA Fine-Tuning|044 Local LoRA Fine-Tuning]] (local backend)
- [[Specs/045 Adapter Inference Export/045 Adapter Inference Export|045 Adapter Inference Export]] (adapter results)
- `anvil/services/compute/{resolve.py,registry.py,result.py}`

## Artifacts

- [[046 Fine-Tune Compute Routing - spec|spec]]

## References

- [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc]]
- [[Reference/FineTuningArchitectureDecisions|Fine-Tuning Architecture Decisions]]
- [[Specs/Specs|Specs]]
