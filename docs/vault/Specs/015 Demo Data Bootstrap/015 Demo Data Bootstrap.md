---
title: 015 Demo Data Bootstrap
type: spec
tags:
  - type/spec
  - domain/training
spec-refs:
  - docs/vault/Specs/015 Demo Data Bootstrap/
status: draft
created: '2026-06-19'
updated: '2026-06-22'
aliases:
  - 015 Demo Data Bootstrap
---

# 015 Demo Data Bootstrap

## Summary

- Q: How should the ops menu re-bootstrap button report results (success/error/summary) to the user? → A: Follow the existing ops page toast pattern (`showToast()`), consistent with all other ops action feedback. Brief green/red toast for success/error; button shows loading spinner during the API call; full result summary (created/skipped/error counts) logged to browser console for debugging.

## Artifacts

- [[015 Demo Data Bootstrap - data-model|data-model]]
- [[015 Demo Data Bootstrap - plan|plan]]
- [[015 Demo Data Bootstrap - quickstart|quickstart]]
- [[015 Demo Data Bootstrap - research|research]]
- [[015 Demo Data Bootstrap - spec|spec]]
- [[015 Demo Data Bootstrap - tasks|tasks]]

## References

- [[Specs/Specs|Specs]]
