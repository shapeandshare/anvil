---
aliases:
  - 'TrackingService Silently Swallows Audit Events'
code-refs:
  - anvil/services/tracking/tracking.py
  - anvil/services/governance/audit_service.py
created: '2026-06-19'
source: agent
status: draft
tags:
  - type/discovery
  - domain/tracking
title: TrackingService Silently Swallows Audit Events
type: discovery
updated: '2026-06-19'
---
# Discovery: TrackingService Silently Swallows Audit Events

## What was found

`TrackingService.log_dataset_lifecycle_event()` and `log_corpus_lifecycle_event()` in `anvil/services/tracking/tracking.py` wrap their entire body in try/except blocks that catch all exceptions and silently set `self._degraded = True`. Return values (`""` on failure) are ignored by callers. This means lifecycle events can silently fail to record without any visibility to users or operators.

## Impact

- False sense of auditability: the system appears to track events but may silently drop them.
- FR-011 in the governance feature explicitly requires surfacing audit-write failures.

## Resolution

The new `AuditService` in `anvil/services/governance/audit_service.py` deliberately **raises** on write failure — the caller's transaction is rolled back so silent data loss cannot happen. `AuditService` is used as the new canonical audit trail; `TrackingService` remains only for MLflow experiment metadata, not authoritative lifecycle records.

## References
- [[Discoveries/Discoveries|Discoveries]]

- `anvil/services/tracking/tracking.py` — `log_dataset_lifecycle_event()`
- `anvil/services/governance/audit_service.py` — `record()` (raises on failure)
