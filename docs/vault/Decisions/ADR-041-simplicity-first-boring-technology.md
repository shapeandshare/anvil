---
title: 'ADR-041: Simplicity First (Boring Technology)'
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/architecture
created: '2026-06-22'
updated: '2026-06-22'
source: agent
code-refs:
  - .specify/memory/constitution.md
  - AGENTS.md
  - .specify/templates/plan-template.md
aliases: 'ADR-041: Simplicity First (Boring Technology)'
---
# ADR-041: Simplicity First (Boring Technology)

## Status

Accepted

## Context

The constitution and agent guidance (`AGENTS.md`) encoded many discipline
rules (layering, typing, TDD, lean dependencies) but had **no explicit,
binding principle that biases every change toward the simplest, most boring
solution**. The closest neighbors were Article II (Educational Clarity —
about readability), Article I (Zero-Dependency Core — scoped to
`anvil/core/`), and the "Lean dependencies" Additional Constraint
(scoped to new pip deps).

The gap let agents and contributors reach for clever, novel, or speculative
designs — new dependencies, premature abstractions, configuration knobs with
no present consumer, or unproven patterns — without having to weigh a simpler
proven alternative. Two concrete failure shapes recur:

1. **Untested complexity shipped as "done"** — an elaborate approach that
   cannot be (or has not been) tested is treated as complete.
2. **Speculative generality** — abstractions and flexibility added for
   hypothetical future requirements that never arrive.

The plan template already contained a **Complexity Tracking** table
(`Violation | Why Needed | Simpler Alternative Rejected Because`), but nothing
in governance *required* its use or made unjustified complexity reject-worthy.

## Decision

Add **Article XI — Simplicity First (Boring Technology)** to the canonical
constitution (`.specify/memory/constitution.md`) as a **hard MUST gate**, and
bump the constitution version **1.7.0 → 1.8.0** (MINOR: new principle).

Article XI codifies six sub-rules:

| § | Rule |
|---|------|
| §11.1 | Choose the simplest approach that meets the requirement; complexity is never the default and must be justified by a present need. |
| §11.2 | Prefer boring, mature, proven technology/patterns over novel/clever/unproven; a novel choice requires a rejected simpler alternative recorded in an ADR or the plan's Complexity Tracking table. |
| §11.3 | YAGNI — build only what the current requirement needs; no speculative generality or premature abstraction. |
| §11.4 | Reuse existing libraries/patterns/abstractions before introducing new ones. |
| §11.5 | Any deviation from the simplest viable solution MUST be recorded in the Complexity Tracking table; an unrecorded complexity-add fails the Constitution Check. |
| §11.6 | Untested/untestable approaches are not "done"; a simpler testable approach is always preferred (pairs with Article IV TDD). |

This decision also propagates the principle to dependent artifacts:

- **`AGENTS.md`** — new Behavioral Principle 13 (Simplicity First) plus an
  Architecture Rules bullet, so the rule appears where agents actually read.
- **`.specify/templates/plan-template.md`** — the Constitution Check gate now
  explicitly names the Article XI simplicity gate and points at the existing
  Complexity Tracking table as the justification record.

## Consequences

### Positive

- A single, citable rule makes "favor simple and boring over untested or
  complex" enforceable at merge review rather than a matter of taste.
- The pre-existing Complexity Tracking table gains teeth — it is now the
  required home for any justified deviation.
- Reduces dependency sprawl, premature abstraction, and unproven-pattern risk.

### Negative

- Genuinely-warranted complexity now carries documentation overhead (a
  Complexity Tracking row). This is intentional friction.
- "Simplest viable" and "boring" require judgment; borderline cases will need
  reviewer discretion.

### Neutral

- No code changes; this is a governance + agent-instruction amendment.
- Reinforces, and is bounded by, Article I (Zero-Dependency Core),
  Article II (Educational Clarity), and Article IV (TDD Mandatory).

## Compliance

- **Merge review** verifies that any added complexity (new dependency, new
  abstraction, novel pattern) has a corresponding Complexity Tracking row
  naming the rejected simpler alternative; missing justification is
  reject-worthy.
- **Constitution Check** in `/speckit.plan` fails when a plan adds complexity
  without recording it per §11.5.
- The constitution Sync Impact Report records the 1.7.0 → 1.8.0 bump and the
  propagation status of every dependent artifact.
