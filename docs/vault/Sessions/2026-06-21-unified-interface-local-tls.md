---
created: '2026-06-21'
updated: '2026-06-21'
source: agent
title: Unified Single-Origin Interface and Local TLS — ADR-037 + Spec 019
type: session-log
aliases:
  - Unified Single-Origin Interface and Local TLS — ADR-037 + Spec 019
  - Single Front Door session
tags:
  - type/session-log
  - domain/architecture
  - domain/infrastructure
  - domain/operations
  - status/reviewed
related:
  - '[[Decisions/ADR-037-unified-interface-local-tls]]'
  - '[[Decisions/ADR-035-mlflow-reverse-proxy]]'
  - '[[Decisions/ADR-036-header-based-api-versioning]]'
---

# Unified Single-Origin Interface and Local TLS — ADR-037 + Spec 019

**Date:** 2026-06-21
**Author:** Sisyphus (agent)

## Summary

Captured a product-level architecture principle as a first-class decision and
feature spec: external consumers must experience anvil as a **single project on
one URL/origin** — even though it internally combines the FastAPI API, the
MLflow tracking server, and (in SaaS) more managed services — and **TLS must
work locally** while keeping the **pip-install-only** experience, with a
parallel **SaaS** variant.

This work followed the OWASP remediation effort (spec 017) and its adversarial
review, which produced the MLflow reverse proxy (ADR-035) and header-based API
versioning (ADR-036). ADR-037 generalizes the single-front-door pattern that
ADR-035 introduced for MLflow.

## Decisions

- **ADR-037 — Unified Single-Origin Interface and Working Local TLS** (proposed).
  - **One origin:** the anvil app is the only externally reachable endpoint;
    secondary services (MLflow now, others later) bind loopback-only with
    unpublished ports and are reverse-proxied under sub-paths via a **proxy
    registry** (generalizes ADR-035).
  - **Local TLS, pip-only:** uvicorn serves HTTPS from a self-signed cert
    auto-generated on first run via `cryptography` (already resolved
    transitively; promoted to a direct dependency). SANs cover
    localhost/127.0.0.1/LAN; cert stored `0600` under the data dir.
  - **Scheme-aware URLs:** browser-facing URL builders honor `https` /
    `X-Forwarded-Proto` and emit the unified-origin path, never a bare `:5001`.
  - **Local/SaaS parity:** shared front-door + proxy-registry code; mode
    differences (cert source, upstream addresses, auth scheme, TLS termination)
    confined to config and `anvil/_saas/`. SaaS keeps edge-terminated TLS
    (CloudFront/ALB per ADR-030).

## Clarifications resolved this session

- Local TLS mechanism → uvicorn + auto self-signed cert (no Caddy/nginx/mkcert).
- Interface model → one port, path-proxied services behind a registry.
- Packaging → new ADR (ADR-037) + new spec (019), cross-referenced from specs
  017/014/018.

## Artifacts

- `docs/vault/Decisions/ADR-037-unified-interface-local-tls.md`
- `specs/024-unified-interface-local-tls/spec.md` (FR-001..FR-010, SC-001..SC-007,
  3 user stories, edge cases, assumptions)
- `specs/024-unified-interface-local-tls/checklists/requirements.md`
- ADR index (`docs/vault/Decisions/README.md`) updated; `.specify/feature.json`
  pointed at spec 019.

## Non-obvious constraints discovered

- `re`-less detail aside: TLS cert generation needs `cryptography` (stdlib `ssl`
  cannot mint certs). It was already in the resolved tree transitively, so
  promoting it to a direct dependency adds no net footprint.
- The single-front-door principle was already half-present: ADR-035 (MLflow
  proxy) and SaaS spec 014 (CloudFront/ALB single origin) — ADR-037 names the
  general principle and adds the missing pip-only local TLS mechanism.
- Spec 017 set HSTS + `Secure` cookies but local mode was plain HTTP, so those
  controls were inert; local TLS makes them effective.

## Validation

- `anvil-vault check-adrs`: all ADRs valid and unique (ADR-037 is the next
  number after main's ADR-034 and the merged ADR-035/036).
- `anvil-vault audit`: 0 errors.

## Follow-ups

- `/speckit.plan` for spec 019: cert-generation module, uvicorn HTTPS wiring in
  `serve()`, proxy registry (refactor ADR-035's MLflow proxy into it),
  scheme-aware URL builders, and healthcheck/SSE/test updates for HTTPS.
- Sequence relative to spec 017 implementation and spec 018 (`/v1/` removal moves
  proxy sub-paths off `/v1/`).
