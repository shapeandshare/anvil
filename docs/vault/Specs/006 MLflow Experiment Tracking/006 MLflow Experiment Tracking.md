---
title: 006 MLflow Experiment Tracking
type: spec
tags:
  - type/spec
  - domain/tracking
spec-refs:
  - docs/vault/Specs/006 MLflow Experiment Tracking/
status: draft
created: '2026-06-13'
updated: '2026-06-22'
aliases:
  - 006 MLflow Experiment Tracking
---

# 006 MLflow Experiment Tracking

## Summary

- Q: MLflow is imported but not declared in any dependency file (version unconstrained). What version should be pinned, and is the managed-evaluation-dataset capability (MLflow 3.x) first-class or fallback-only? → A: Pin `mlflow>=3.1` as an explicit dependency; managed evaluation datasets (US6 / FR-021) are a first-class supported path, with capability detection as a safety net rather than the primary mode.

## Artifacts

- [[006 MLflow Experiment Tracking - data-model|data-model]]
- [[006 MLflow Experiment Tracking - plan|plan]]
- [[006 MLflow Experiment Tracking - quickstart|quickstart]]
- [[006 MLflow Experiment Tracking - research|research]]
- [[006 MLflow Experiment Tracking - spec|spec]]
- [[006 MLflow Experiment Tracking - tasks|tasks]]

## References

- [[Specs/Specs|Specs]]
