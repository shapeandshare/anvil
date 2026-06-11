---
title: Open Questions
type: reference
tags: [type/reference, domain/governance]
created: 2026-06-10
updated: 2026-06-10
---

# Open Questions

- How should MLflow be integrated with training service (subprocess vs in-process)?
  → **Resolved**: MLflow runs as a managed subprocess via ProcessSupervisor
- Should progressive walkthrough files (train1-5) contain full implementations or stubs?
  → **Deferred**: Stubs for now; full implementations in future iteration
- What is the long-term storage strategy for model checkpoints beyond local filesystem?
  → **Planned**: S3 backend via FileStore abstraction in v2