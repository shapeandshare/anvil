---
title: 040 External Model Registry
type: spec
tags:
  - type/spec
  - domain/training
  - domain/tracking
spec-refs:
  - docs/vault/Specs/040 External Model Registry/
status: draft
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - 040 External Model Registry
---

# 040 External Model Registry

Track B foundation of the [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|Fine-Tuning Arc]]: a
source-agnostic import paradigm (`ModelSource`) that brings external models into anvil as tracked
metadata entries — created before any weights download. HuggingFace Hub first, local-file second.

## Owned

- **FRs**: FR-005, FR-006, FR-009 (+ FR-005a, FR-006a)
- **Decisions**: FT-AD-4

## Dependencies

- [[Specs/003 Model Registry Tracking/003 Model Registry Tracking|003 Model Registry Tracking]]
- `huggingface_hub` (behind `[finetune]` extra) for the HF source

## Artifacts

- [[040 External Model Registry - spec|spec]]

## References

- [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc]]
- [[Reference/FineTuningArchitectureDecisions|Fine-Tuning Architecture Decisions]]
- [[Specs/Specs|Specs]]
