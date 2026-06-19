---
title: Tag Vocabulary
type: reference
tags:
  - type/reference
  - domain/vault
created: 2026-06-18
updated: 2026-06-18
aliases:
  - Tag Vocabulary
---

# Tag Vocabulary

The controlled tag vocabulary for the anvil vault. Every tag used in any vault note MUST come from this list. Adding a new tag requires updating this file first.

Tags are organized into axes. A note may carry multiple tags across axes; within the `type/*` and `status/*` axes a note carries at most one tag.

## `type/*` — Note Type (REQUIRED, singular)

Every note has exactly one `type/*` tag. Determines template and content structure.

- `type/principle` — Governance and constitutional notes. Non-negotiable rules.
- `type/design` — Conceptual intent: architecture decisions, rationale, theses.
- `type/system` — A bounded implemented subsystem. Carries `code-refs:`.
- `type/reference` — Glossary, guides, reference material, MOCs of reference material.
- `type/moc` — Map of Content (folder or domain tier).
- `type/decision` — An architecture or content decision. Written to `Decisions/` as ADRs.
- `type/discovery` — A non-obvious constraint, gap, or conflict found during a session. Written to `Discoveries/`.
- `type/session-log` — Session activity log; permanent audit trail. Written to `Sessions/`. Append-only.

## `domain/*` — Domain (0 or more)

Groups notes across folders by subject area.

- `domain/architecture` — System architecture, data flow, layer discipline.
- `domain/core` — Core training engine, autograd, tokenizer.
- `domain/training` — Training pipeline, hyperparameters, walkthroughs.
- `domain/inference` — Inference service, sampling, generation.
- `domain/export` — Model export, safetensors, HuggingFace interop.
- `domain/ui` — Frontend, design system, CSS tokens, components.
- `domain/database` — SQLAlchemy models, repositories, migrations, data management.
- `domain/operations` — MLflow, supervisor, process management, service health, experiment tracking, MLops.
- `domain/mlops` — ML lifecycle, operations infrastructure, deployment automation.
- `domain/tracking` — Experiment tracking, MLflow integration, metrics collection.
- `domain/infrastructure` — Deployment, CI/CD, docker, cloud infrastructure, GPU platforms.
- `domain/registry` — Model registry, artifact storage, versioning.
- `domain/tooling` — Health tooling, audits, CI/CD, automation.
- `domain/vault` — Vault structure, MOCs, tags, frontmatter conventions.
- `domain/governance` — Constitution, policies, principles.
- `domain/mcp` — MCP exposure layer.
- `domain/content` — Learning content, walkthroughs, documentation.

## `status/*` — Note State (0 or 1; omit if stable)

Authorship lifecycle.

- `status/draft` — Newly authored, unverified. Excluded from auto-injection. Default for agent notes.
- `status/wip` — Actively being worked, not yet verifiable.
- `status/reviewed` — Verified against sources this session. Eligible for auto-injection. Agent may set.
- `status/canonical` — Human-ratified as authoritative. **Human-only.**

## Staleness Fields (frontmatter, not tags)

Orthogonal to `status/*`. Set by health tooling, cleared by humans.

- `stale: true` — a note's `code-refs:` or referenced sources no longer hold.
- `stale_reason:` — required when `stale: true`; states what is stale.