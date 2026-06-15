## Open Questions

- How should MLflow be integrated with training service (subprocess vs in-process)?
  → **Resolved**: MLflow runs as a managed subprocess via ProcessSupervisor
- Should progressive walkthrough files (train1-5) contain full implementations or stubs?
  → **Deferred**: Stubs for now; full implementations in future iteration
- What is the long-term storage strategy for model checkpoints beyond local filesystem?
  → **Planned**: S3 backend via FileStore abstraction in v2
- Could the `section-card__header--clickable` + `section-card__content-collapsible` pattern be extracted into a reusable partial or web component? It's now used in two places (training output, ops logs).
  → **Deferred**: Next UI consolidation pass
- Could the [[wizard-stepper-pattern]] be extracted into a reusable partial or web component? Currently inlined in training.html. Would benefit dataset curation, corpus ingestion flows.
  → **Deferred**: Next UI consolidation pass