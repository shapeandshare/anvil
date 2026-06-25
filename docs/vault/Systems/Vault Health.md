---
title: Vault Health
type: system
tags:
  - type/system
  - domain/tooling
  - domain/vault
created: 2026-06-18
updated: 2026-06-18
aliases:
  - Vault Health
---

# Vault Health

How the vault stays coherent over time: orphan prevention, broken-link detection, frontmatter validation, and staleness tracking.

## Responsibility

Reconcile the high coverage of an agent-first vault with long-term signal integrity — preventing the vault from rotting into accumulated noise.

## How it works

- **Frontmatter validation.** Every note must carry `title`, `type`, `tags`, `created`, `updated`. Tags must come from the controlled vocabulary at `_meta/tags.md`. The audit script flags violations.
- **Wikilink resolution.** Every `[[wikilink]]` must resolve to an existing note. Broken links are errors.
- **Orphan detection.** A note with no inbound wikilinks is an orphan — it exists outside the graph. MOCs and session logs are exempt.
- **Controlled vocabulary.** All tags must be in `_meta/tags.md`. Adding a new tag requires editing that file first.
- **Staleness.** When a note's `code-refs:` or sources no longer hold, it is marked `stale: true` with a `stale_reason:`. Only a human clears staleness.
- **Graph health.** Optional networkx analysis (orphan rate, PageRank, communities, temporal decay) generates a weighted health score.

## Interfaces

Run via Makefile targets using the project venv:

| Command | Effect |
|---------|--------|
| `make vault-audit` | Mechanical audit + graph health (report only) |
| `make vault-audit-apply` | Auto-fix safe issues (aliases, tag casing, missing dates) |
| `make vault-audit-diff` | Preview auto-fixes without writing |
| `make vault-audit-fast` | Skip networkx graph health pass |

## References
- [[Systems/Systems|Systems]]

- `scripts/ci/vault_audit.py` — Mechanical audit driver
- `scripts/ci/graph_health/` — Optional networkx graph analysis
- `docs/vault/_meta/tags.md` — Controlled tag vocabulary