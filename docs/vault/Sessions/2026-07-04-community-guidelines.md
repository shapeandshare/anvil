---
title: "Session: Community Guidelines and Agent-Native Open-Source Behavior"
type: session-log
tags:
  - type/session-log
  - domain/governance
  - status/draft
created: '2026-07-04'
updated: '2026-07-04'
aliases:
  - community-guidelines
status: draft
source: agent
---

# Session: Community Guidelines and Agent-Native Open-Source Behavior

**Date**: 2026-07-04
**Trigger**: User wanted to add community guidelines and behavior docs to the
project, then asked that they properly account for the project's AI-native /
agentic development nature.

## Summary

Researched how major Python OSS projects (pytest, Flask, HuggingFace
transformers, scikit-learn, Django) structure their community guidelines, and
GitHub's community profile system. Found that anvil had only `CONTRIBUTING.md`
(dev-setup focused) and `CODEOWNERS` — no `CODE_OF_CONDUCT.md`, `SECURITY.md`,
`SUPPORT.md`, issue/PR templates, or community section in `README.md`.

Drafted and iterated the full set of community documents. After the first draft,
the user flagged that the AI contribution section was too defensive for a
project that is *developed and maintained primarily through AI agents*. Rewrote
the entire approach to be agent-native:

1. **Researched** patterns from 5 major Python projects + GitHub community
   standards documentation (via parallel librarian agents).
2. **Created 7 new files**: CODE_OF_CONDUCT.md (Contributor Covenant v2.1 +
   AI agent liability clause), SECURITY.md (GH Advisories + ML-specific
   warnings), SUPPORT.md (issues/discussions + agent behavioral rules),
   `.github/ISSUE_TEMPLATE/bug_report.md`, `feature_request.md`,
   `documentation.md`, and `.github/PULL_REQUEST_TEMPLATE.md`.
3. **Updated 3 files**: CONTRIBUTING.md (added Community Guidelines + full
   Agentic Development section framing agentic contribution as the primary
   workflow), README.md (badges + Community section), `docs/vault/Decisions/README.md`
   (ADR-049 index entry).
4. **Wrote ADR-049** documenting the full rationale, including the agent-native
   framing decisions (CoC agent liability clause, self-identification
   requirement, three-tier contribution policy, template provenance fields).

### Key design decisions

- **Agent-native framing**: The project is developed primarily through AI
  agents. Rather than treating AI contributions as an exceptional case, the
  guidelines frame agentic contribution as the normal, primary workflow.
- **Three tiers**: Human contributors using AI tools / Autonomous agents /
  Rejected contributions — each with clear, distinct expectations.
- **CoC agent liability**: The human operator who deploys/configures an agent
  bears responsibility for its behavior. Closes a gap standard CoC templates
  don't address.
- **Self-identification**: All templates include structured provenance fields
  (agent identity, operating mode, discovery methodology) so maintainers can
  evaluate contributions with appropriate context.

## Files Changed

### New

- `CODE_OF_CONDUCT.md` — Contributor Covenant v2.1 + AI agent liability clause
- `SECURITY.md` — GitHub Security Advisories, ML-specific warnings
- `SUPPORT.md` — Issues/Discussions guidance + agent behavioral rules
- `.github/ISSUE_TEMPLATE/bug_report.md` — Structured bug report + agent-origin fields
- `.github/ISSUE_TEMPLATE/feature_request.md` — Feature request + agent-origin fields
- `.github/ISSUE_TEMPLATE/documentation.md` — Documentation issue template
- `.github/PULL_REQUEST_TEMPLATE.md` — PR template with provenance + agent session context
- `docs/vault/Decisions/ADR-049-community-guidelines.md` — Architecture Decision Record

### Modified

- `CONTRIBUTING.md` — Added Community Guidelines + Agentic Development section
- `README.md` — Badges (CoC + Contributing), Community section
- `docs/vault/Decisions/README.md` — ADR-049 index entry

## Agents Used

- **Librarian** (×2, parallel) — researched community guidelines patterns and
  GitHub community standards documentation
- **Sisyphus** — orchestration, drafting, ADR writing

## Discoveries

- The project's AI-native development model means standard "AI contribution
  policy" templates are a poor fit — they treat AI work as exceptional when it
  is actually the norm.
- Contributor Covenant v2.1's graduated enforcement (correction → warning →
  temp ban → permanent ban) provides a clearer framework than v1.4, especially
  for a project that may need to address agent behavior.
- GitHub auto-links CODE_OF_CONDUCT.md, SECURITY.md, and SUPPORT.md from the
  sidebar only when they are in the *root* directory (not `.github/` or `docs/`).

## ADRs

- [[Decisions/ADR-049-community-guidelines|ADR-049: Community Guidelines and Open-Source Behavior]]

## Related

- [[Discoveries/relative-import-mass-conversion|Relative Import Mass Conversion]] (precedent for AI-native policy)
- [[Sessions/2026-06-19-responsible-data-governance|2026-06-19: Responsible Data Governance]]
- [[Sessions/2026-06-19-saas-spec-hardening|2026-06-19: SaaS Spec Hardening]]