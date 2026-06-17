---
title: Open Questions
type: reference
tags:
  - type/reference
  - domain/governance
created: 2026-06-10T00:00:00.000Z
updated: '2026-06-16T00:00:00.000Z'
---

# Open Questions

- How should MLflow be integrated with training service (subprocess vs in-process)?
  → **Resolved**: MLflow runs as a managed subprocess via ProcessSupervisor
- Should progressive walkthrough files (train1-5) contain full implementations or stubs?
  → **Resolved (2026-06-14)**: Full implementations. The Llama engine evolution updated all 6 walkthroughs (train0.py–train5.py) to teach the Llama architecture progression with complete, runnable implementations and a safetensors export demo in train5.
- What is the long-term storage strategy for model checkpoints beyond local filesystem?
  → **Planned**: S3 backend via FileStore abstraction in v2
- Could the `section-card__header--clickable` + `section-card__content-collapsible` pattern be extracted into a reusable partial or web component? It's now used in two places (training output, ops logs).
  → **Deferred**: Next UI consolidation pass
- Could the [[wizard-stepper-pattern]] be extracted into a reusable partial or web component? Currently inlined in training.html. Would benefit dataset curation, corpus ingestion flows.
  → **Deferred**: Next UI consolidation pass
- Should detailed learning content about data flow, export pipeline, hyperparameters, and dual backend be part of the walkthrough library?
  → **Resolved (2026-06-15)**: 6 new vault reference docs and 2 new walkthroughs added. Covered: safetensors export, HF interop, dual backend bridge, hyperparameter interactions, progressive walkthrough reference, MLflow integration, end-to-end data flow.
- Should the app ship a `manifest.json` for full PWA support? Favicons are now in place (`favicon.svg` + `apple-touch-icon.png`). A web app manifest would add home-screen name/display/theme-color for iOS/Android installs. `theme_color: #000000` and `background_color: #1c1c1e` align with existing forge dark palette.
  → **Open**
- `train_torch()` runs as a single-example, single-token Python loop (`for pos_id in range(n)`) — no batching, no vectorized sequence dimension. This means anvil is CPU-bound even on GPU hardware. Batching the sequence dimension is the single highest-leverage prerequisite before any GPU vendor choice matters.
  → **Open — planned as engine evolution work. See [[Decisions/ADR-014-ml-infrastructure-tier-strategy]] and [[Reference/InfraParadigms]].**
