---
title: >-
  Session: SaaS Spec Hardening — Observability, MLflow Proxy, Cluster Admin,
  Resilience
type: session-log
tags:
  - type/session-log
  - domain/architecture
  - domain/infrastructure
  - domain/operations
  - domain/governance
created: '2026-06-19'
updated: '2026-06-19'
aliases:
  - >-
    Session: SaaS Spec Hardening — Observability, MLflow Proxy, Cluster Admin,
    Resilience
  - saas-spec-hardening
source: agent
status: draft
---
# Session: SaaS Spec Hardening — Observability, MLflow Proxy, Cluster Admin, Resilience

**Date**: 2026-06-19
**Trigger**: User explored the SaaS architecture spec and vault diagrams, then drove a series of
enhancements: observability (logs/traces/metrics), MLflow UI access in SaaS mode, an admin-user
model spanning local and SaaS, multi-cluster CLI management, and finally a critical multi-lens
review (distributed-systems architect, DevOps/SRE, principal engineer) whose findings were all
addressed.

Spec under work: `docs/vault/Specs/016 SaaS Architecture/spec.md` (+ `plan.md`). See [[Decisions/ADR-030-saas-architecture|ADR-030]].

## What was done

### 1. Fixed a Mermaid parse error
`docs/vault/Reference/SaaSArchitecture.md` three-mode diagram had a malformed node
(`S5[S6 --- S6[Cognito auth...]`). Corrected to `S5 --- S6[Cognito auth...]`.

### 2. Added observability (consulted Oracle on architecture; FR-052–FR-056)
Three pillars, all SaaS-only optional extras, local mode degrades gracefully:

| Pillar | Approach |
|--------|----------|
| Logs | CloudWatch Logs API surfaced in-app via `LogsReader` abstraction (`LocalLogsReader` / `CloudWatchLogsReader`); per-job compute pod logs via `batch_log_stream` column |
| Traces | OpenTelemetry auto-instrumentation → AWS X-Ray; `traceparent` propagated into Batch pods (env var) and across the Redis SSE boundary (message envelope) |
| Metrics | Prometheus `/metrics` (`prometheus-fastapi-instrumentator`) + custom metrics; Prometheus + Grafana + Alertmanager on ECS Fargate; compute pods emit CloudWatch EMF |

### 3. Added MLflow reverse proxy (FR-057)
Browser access to the private MLflow service via an authenticated `/v1/mlflow-proxy/{path:path}`
route on anvil-web. MLflow stays in a private subnet (no ALB/CloudFront/internet route). Resolved
the AJAX/static-path problem with MLflow's `--static-prefix=/v1/mlflow-proxy` (FR-057g).

### 4. Added the cluster-admin model (FR-034–FR-038b)
Two-tier: a system-level `is_cluster_admin` flag above org-scoped RBAC. Local mode runs as an
implicit admin with no auth. Deploy-created user is the initial cluster admin.

### 5. Added multi-cluster CLI management (FR-014/014a/014b/014c)
`anvil remote cluster add/list/remove/configure` + a `~/.anvil/clusters.json` registry (carries
`region` and `api_version`). `deploy init` auto-adds, `deploy destroy` removes. API version
negotiation via `GET /v1/version`.

### 6. Critical review — 14 findings addressed
A three-lens review surfaced one BLOCKING and many HIGH/medium items, all resolved:

| # | Finding | Resolution |
|---|---------|-----------|
| BLOCKING | FR-037 vs FR-038a cluster-admin authority conflict | **Read-wide/write-narrow** model (FR-037a/b): cross-org read + fixed cluster-op action matrix; tenant-data writes still gated by org role |
| HIGH | MLflow proxy AJAX/static paths | `--static-prefix` (FR-057g), fallback `<base href>` rewrite |
| HIGH | Prometheus undersized/ephemeral | 1 vCPU/2 GB, EFS-backed TSDB, rate-limited `ecs_sd_configs`, + Alertmanager (FR-054b/e) |
| DS | Redis single-AZ | Multi-AZ failover (FR-045q) + server-signaled SSE degradation (FR-045r) |
| DS | No region in cluster registry | Added `region` (FR-014a); documented single-region/multi-AZ HA |
| DS | Reconciler underspecified | Period/grace/stateless/idempotent/backoff/heartbeat (FR-044a) |
| DS | `job_events` unbounded growth | Metric throttling, indexes, 30-day archival, autovacuum (FR-043a) |
| SRE | No backup/DR | RDS snapshots+PITR, S3 versioning, destroy final-snapshot, `deploy restore` (FR-058–061) |
| SRE | Secret rotation hand-waved | Dual-key window for SSE signing secret + Redis two-token (FR-045s) |
| SRE | CW Logs cost | SaaS log viewer is manual-refresh only (FR-052c) |
| PE | No API version negotiation | `GET /v1/version` + `min_cli_version` (FR-014c) |
| PE | No CI deploy path | `ANVIL_DEPLOY_*` env + `--json`, OIDC creds (FR-028a) |
| PE | Log viewer hard-fails without monitoring | Null-reader graceful degradation (FR-052d) |
| PE | Extras combinatorics | `saas` composite extra + audience→extra table |

Added acceptance gates **G9** (observability + proxy) and **G10** (resilience/DR); plan phases
**12–14**.

### 7. Git
Committed as a single `docs:` commit on `opencode/curious-sailor`; opened **PR #85** against `main`.

## Key insights

- The cluster-admin "god mode" instinct is dangerous: operational cross-org *visibility* is a
  legitimate need, but it must not silently become cross-org *write* authority. The
  read-wide/write-narrow split (FR-037a/b) is the clean resolution and is reusable for any
  multi-tenant system with a platform-operator role.
- MLflow's SPA emits absolute `/ajax-api/` and `/static-files/` paths; a naive reverse proxy that
  only relies on relative URLs will render a blank UI. `--static-prefix` is the correct fix.
- AGENTS.md "Active Technologies"/"Recent Changes" were intentionally NOT updated: this is a draft
  spec on a feature branch with zero implemented code. Agent memory tracks merged behavior; it will
  be updated when the SaaS implementation lands.

## Follow-ups

- The three SaaS reference diagram docs ([[Reference/SaaSSystemDiagrams]],
  [[Reference/SaaSSecurityAndFlowDiagrams]], [[Reference/SaaSArchitecture]]) predate this session and
  do not yet depict observability, the MLflow proxy, cluster admin, or multi-cluster. Each carries a
  "Pending Updates" stub flagging the gap; full diagram redraw is deferred.
- When SaaS implementation begins, update AGENTS.md Active Technologies + Recent Changes.

## Tags

- type/session-log
- domain/architecture
- domain/infrastructure
- domain/operations
- domain/governance
- status/draft
