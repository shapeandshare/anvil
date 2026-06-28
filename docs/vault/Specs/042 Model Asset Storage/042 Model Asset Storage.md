---
title: 042 Model Asset Storage
type: spec
tags:
  - type/spec
  - domain/training
  - domain/content
spec-refs:
  - docs/vault/Specs/042 Model Asset Storage/
status: draft
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - 042 Model Asset Storage
---

# 042 Model Asset Storage

Track B foundation of the [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|Fine-Tuning Arc]]: download
and track model assets (weights/tokenizer/config) through the existing storage seam — local `FileStore`
now, `VersionedContentStore`/LakeFS under SaaS. Idempotent, checksummed, license-aware.

## Owned

- **FRs**: FR-010..FR-013 (+ FR-010a), FR-030 (weight formats), FR-033 (format detection / fail-closed)
- **Decisions**: FT-AD-5 (references AD-17), FT-AD-11 (format aspect)

## Dependencies

- [[Specs/040 External Model Registry/040 External Model Registry|040 External Model Registry]] (`ExternalModel`)
- [[Specs/019 LakeFS Content Repo/019 LakeFS Content Repo|019 LakeFS Content Repo]] (`VersionedContentStore`)
- `anvil/storage/` (`FileStore`)

## Artifacts

- [[042 Model Asset Storage - spec|spec]]

## References

- [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc]]
- [[Reference/FineTuningArchitectureDecisions|Fine-Tuning Architecture Decisions]]
- [[Specs/Specs|Specs]]
