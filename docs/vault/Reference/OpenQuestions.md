---
title: Open Questions
type: reference
tags:
  - type/reference
  - domain/governance
created: 2026-06-10T00:00:00.000Z
updated: '2026-06-14T00:00:00.000Z'
---

# Open Questions

- How should MLflow be integrated with training service (subprocess vs in-process)?
  → **Resolved**: MLflow runs as a managed subprocess via ProcessSupervisor
- Should progressive walkthrough files (train1-5) contain full implementations or stubs?
  → **Resolved (2026-06-14)**: Full implementations. The Llama engine evolution updated all 6 walkthroughs (train0.py–train5.py) to teach the Llama architecture progression with complete, runnable implementations and a safetensors export demo in train5.
- What is the long-term storage strategy for model checkpoints beyond local filesystem?
  → **Planned**: S3 backend via FileStore abstraction in v2
