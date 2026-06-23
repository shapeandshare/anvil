---
title: Header-Based API Versioning and URL Path De-Versioning
type: decision
status: draft
source: agent
created: '2026-06-21'
updated: '2026-06-21'
aliases:
  - Header-Based API Versioning
  - ADR-036
related:
  - '[[Decisions/ADR-032-greenfield-legacy-removal]]'
  - '[[Decisions/ADR-030-saas-architecture]]'
code-refs:
  - anvil/api/v1/router.py
  - anvil/api/app.py
  - docs/vault/Specs/023 Header API Versioning/spec.md
tags:
  - type/decision
  - domain/architecture
  - domain/operations
  - status/draft
---

# ADR-036: Header-Based API Versioning and URL Path De-Versioning

## Status

proposed

## Context

The anvil HTTP API embeds its version in the URL path: every route lives under
`/v1/` (e.g. `/v1/training/start`, `/v1/datasets`, and the page routes
`/v1/datasets-page`, `/v1/learn/*`). This URL-embedded version was introduced
defensively, anticipating a future where `/v2/` would coexist with `/v1/` for
backward compatibility.

That premise does not hold for anvil:

- Per **ADR-032 (Greenfield Legacy Removal)**, anvil has no users, no
  deployments, no released API contract, and explicitly does **not** maintain
  backward-compatibility, legacy, upgrade-path, or compatibility-layer
  machinery while greenfield.
- URL-embedded versioning conflates two unrelated concerns in one path prefix:
  API *endpoints* and server-rendered *pages* both live under `/v1/`. This
  collision actively harmed the security remediation (spec 017): the auth
  middleware could not classify "API vs page" by prefix, because both share
  `/v1/` (see ADR-035 / spec 017 auth-middleware contract).
- URL-embedded versions are the least flexible versioning scheme: they force a
  full path migration for any version bump and leak a version into every link,
  bookmark, template, and client.

A cleaner approach for a single-shipped-version, greenfield project is to drop
the version from the URL entirely and, *if and when* versioning is ever needed,
negotiate it via an HTTP header (e.g. `Accept: application/vnd.anvil.v2+json` or
`X-Anvil-API-Version: 2`). This keeps URLs stable and decouples version
negotiation from routing.

## Decision

Adopt **header-based API versioning** and remove the version from URL paths.
This is a deliberate, greenfield, one-time breaking change with **no
backward-compatibility, no `/v1/` alias, no redirect shim, and no migration
layer** (consistent with ADR-032).

1. **Remove the `/v1/` prefix from all routes.** API endpoints move to their
   bare paths (e.g. `/training/start`, `/datasets`, `/health`). Page routes
   move to clean paths (e.g. `/datasets`, `/learn/*`, `/training`), with the
   `-page` suffix convention reconsidered as part of the migration.
2. **Negotiate version via header, default to current.** A single optional
   request header selects the API version. Absent the header, the request
   targets the current (and only) version. No version in the URL.
3. **Separate API and page route namespaces** so the auth middleware can
   classify them without prefix ambiguity (this directly unblocks the spec 017
   auth design). Options: mount the JSON API under a non-versioned `/api`
   namespace and pages at the root, OR maintain an explicit page-route registry.
   The chosen scheme is specified in spec 018.
4. **No compatibility surface.** No `/v1/*` → new-path redirects, no dual
   registration, no deprecation window. All internal callers (templates, static
   JS `fetch`/`EventSource` URLs, tests, CLI references, the Docker healthcheck,
   the MLflow proxy route from ADR-035) are updated in the same change.

This decision is scoped to a **separate feature/spec (`018-header-api-versioning`)**
and is intentionally NOT bundled into the OWASP remediation (spec 017), because
it is a large mechanical migration touching ~125 routes, all templates, and all
client JS. Spec 017's auth contract is written to be compatible with both the
current `/v1/` layout (via an explicit page-route registry) and the post-018
layout.

## Consequences

**Easier:**

- URLs are stable and human-friendly; no version churn on links/bookmarks.
- The auth middleware classifies API vs page routes cleanly, removing the
  prefix-collision footgun that complicated spec 017.
- Future versioning (if ever needed) is a header negotiation, not a path
  migration — additive and non-breaking.
- One fewer concept ("what does `/v1/` mean here?") for newcomers.

**Harder / risks:**

- Large mechanical blast radius: ~125 routes across 17 route files, every Jinja2
  template link, every static JS `fetch`/`EventSource` URL, the Docker
  healthcheck target, tests, and the MLflow proxy path. All must change
  atomically (greenfield license per ADR-032 — no compat shim to soften it).
- Any external bookmark or script hitting `/v1/...` breaks with no redirect.
  Acceptable given zero deployments (ADR-032 precondition).
- Ordering dependency with spec 017: if 017 (auth) ships first, its auth
  contract must use the explicit page-route registry; 018 then simplifies it. If
  018 ships first, 017's classification is trivially clean. Either order works;
  the dependency is documented in both specs.

## Compliance

- `grep` confirms zero `/v1/` literals remain in `anvil/api/`, templates,
  static JS, the Makefile/compose healthcheck, and tests after the migration
  (allowing only the header-version constant).
- An integration test asserts bare paths resolve (e.g. `GET /health` → 200) and
  that the old `/v1/health` returns 404 (no compat alias).
- A version-negotiation test asserts the optional version header is parsed and
  an unknown version yields a clear 400.
- The spec 017 auth middleware and the ADR-035 MLflow proxy route reference the
  new (non-`/v1/`) paths after 018 lands; before 018, they use the page-route
  registry.
