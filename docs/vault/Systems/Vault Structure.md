---
title: Vault Structure
type: system
tags:
  - type/system
  - domain/vault
created: 2026-06-18
updated: 2026-06-18
aliases:
  - Vault Structure
---

# Vault Structure

The directory layout, naming conventions, and organizational principles of the anvil vault.

## Directory Layout

```
docs/vault/
├── Governance/          # Constitution, policies, principles
│   └── Constitution.md  # Canonical constitution (source: .specify/memory/)
├── Design/              # Conceptual design and rationale
│   └── Design.md        # MOC
├── Systems/             # Implemented subsystems and tooling
│   ├── Vault Health.md  # Audit & graph health tooling
│   └── Vault Structure.md # This file
├── Decisions/           # Architecture Decision Records (ADRs)
│   ├── ADR-NNN-*.md     # Individual ADRs
│   └── ADR-template.md  # Template for new ADRs
├── Reference/           # Glossary, guides, reference material
│   ├── ArchitectureOverview.md
│   ├── Glossary.md
│   └── ...
├── Discoveries/         # Non-obvious constraints (episodic)
│   └── Discoveries.md   # MOC
├── Sessions/            # Session logs (append-only)
│   ├── YYYY-MM-DD-*.md
│   └── ...
├── _meta/               # Vault infrastructure
│   ├── tags.md          # Controlled tag vocabulary
│   ├── templates/       # Note templates
│   └── audit/           # Audit reports (gitignored)
└── index.md             # Vault entry point
```

## Naming Conventions

| Note Type | Pattern | Example |
|-----------|---------|---------|
| ADR | `ADR-NNN-slug.md` | `ADR-007-llama-engine-evolution.md` |
| Session | `YYYY-MM-DD-description.md` | `2026-06-14-llama-engine-evolution.md` |
| Reference | `CamelCase.md` | `ArchitectureOverview.md` |
| System | `Title Case.md` | `Vault Health.md` |
| Discovery | `Title Case.md` | `(alphanumeric with spaces).md` |

## Frontmatter Conventions

Every note requires:
- `title:` — Human-readable name
- `type:` — Note type (reference, session, decision, etc.)
- `tags:` — Array of controlled vocabulary tags
- `created:` — ISO 8601 date or datetime
- `updated:` — ISO 8601 date or datetime

Recommended for reference/system notes:
- `aliases:` — Array of lowercase-kebab aliases (for Obsidian graph navigation)

## References

- `_meta/tags.md` — Controlled tag vocabulary
- `_meta/templates/` — Note templates