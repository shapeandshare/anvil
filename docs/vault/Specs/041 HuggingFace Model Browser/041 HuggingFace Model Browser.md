---
title: 041 HuggingFace Model Browser
type: spec
tags:
  - type/spec
  - domain/training
  - domain/ui
spec-refs:
  - docs/vault/Specs/041 HuggingFace Model Browser/
status: draft
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - 041 HuggingFace Model Browser
---

# 041 HuggingFace Model Browser

Track B foundation of the [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|Fine-Tuning Arc]]: an in-app
HuggingFace view plus a curated TinyLlama-class catalog with per-model local-eligibility badges. Feeds
the import paradigm (spec 040).

## Owned

- **FRs**: FR-007, FR-008 (+ FR-007a, FR-008a), FR-032 (publish allow-list)
- **Decisions**: FT-AD-8, FT-AD-11 (allow-list aspect)

## Dependencies

- [[Specs/040 External Model Registry/040 External Model Registry|040 External Model Registry]] (import)
- HF Hub API (behind `[finetune]` extra); device detection in `anvil/services/compute/resolve.py`

## Artifacts

- [[041 HuggingFace Model Browser - spec|spec]]

## References

- [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc]]
- [[Reference/FineTuningArchitectureDecisions|Fine-Tuning Architecture Decisions]]
- [[Specs/Specs|Specs]]
