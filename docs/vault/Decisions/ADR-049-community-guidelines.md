---
title: "ADR-049: Community Guidelines and Open-Source Behavior"
type: decision
tags:
  - type/decision
  - domain/governance
created: 2026-07-04
updated: 2026-07-04
aliases:
  - Community Guidelines
source: agent
code-refs:
  - CODE_OF_CONDUCT.md
  - SECURITY.md
  - SUPPORT.md
  - CONTRIBUTING.md
  - .github/ISSUE_TEMPLATE/
  - .github/PULL_REQUEST_TEMPLATE.md
---

# ADR-049: Community Guidelines and Open-Source Behavior

## Status

Accepted

## Context

anvil is a single-developer project (@joshburt) that has published source
code, CI, issue tracking, and a CONTRIBUTING.md focused exclusively on
development setup and CI gates. As the project attracts outside attention
and potential contributions, it lacks several community-standard documents:

1. **Code of Conduct** — no behavioral expectations or enforcement process
   for community interactions.
2. **Security policy** — no documented process for responsible vulnerability
   disclosure, even though anvil handles model weights (pickle/safetensors),
   runs a web server, and supervises an MLflow sidecar.
3. **Support channels** — no guidance on where to ask questions vs. file bugs,
   leading to issue tracker noise.
4. **Contributing guidelines** — existing CONTRIBUTING.md covers dev setup and
   CI gates but has no behavioral/social expectations or guidance for outside
   contributors.
5. **Issue and PR templates** — missing, which means no structured bug/feature
   reporting and no PR checklist.

GitHub's community profile (Insights → Community) scores repositories on
these elements and displays badges in the sidebar for CODE_OF_CONDUCT.md,
SECURITY.md, SUPPORT.md, and CONTRIBUTING.md. Having these files signals
project maturity and makes the project more approachable to new contributors.

## Decision

Adopt a standard set of community guideline documents, following patterns
established by major Python OSS projects (pytest, Flask, HuggingFace
transformers, scikit-learn):

### Files added

| File | Content | Source |
|------|---------|--------|
| `CODE_OF_CONDUCT.md` | Contributor Covenant v2.1 with graduated enforcement | Standard template, maintainer contact set to joshburt@shapeandshare.com |
| `SECURITY.md` | GitHub Security Advisories + email; ML-specific warnings (safetensors/pickle, web server exposure) | Custom, informed by scikit-learn and HuggingFace patterns |
| `SUPPORT.md` | Issues vs. Discussions guidance; pre-ask checklist | Custom, lightweight |
| `.github/ISSUE_TEMPLATE/bug_report.md` | Structured bug report with environment checklist | Standard GitHub template pattern |
| `.github/ISSUE_TEMPLATE/feature_request.md` | Structured feature request | Standard GitHub template pattern |
| `.github/ISSUE_TEMPLATE/documentation.md` | Documentation issue report | Standard GitHub template pattern |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR checklist matching existing CI gates, plus Origin section (agent/human provenance, AGENTS.md compliance) | Custom, matching CONTRIBUTING.md gates, with agent-native fields |

### Files updated

| File | Change |
|------|--------|
| `CONTRIBUTING.md` | Replaced "AI-generated contributions" section with full "Agentic Development" section framing agentic contribution as the project's primary workflow; added autonomous-agent expectations (self-identify, follow AGENTS.md, pass CI gates); added explicit rejection criteria |

### Design decisions

1. **Contributor Covenant v2.1** (not v1.4) — v2.1 adds graduated enforcement
   guidelines (correction → warning → temporary ban → permanent ban), which
   provide a clear escalation path. HuggingFace (closest analog: ML/AI OSS)
   uses v2.1. Pytest/Flask use v1.4 but are older adoptions.

2. **Reporting contact** — single email (`joshburt@shapeandshare.com`) rather than
   a team alias. Appropriate for a single-maintainer project. Can be upgraded
   to a group alias if the maintainer team grows.

3. **Agent-native framing (not just "AI policy")** — anvil is developed and
   maintained primarily through AI agents. Rather than treating AI contributions
   as an exceptional case to be cautiously permitted, the guidelines frame
   agentic contribution as the **normal, primary workflow**. Three tiers are
   defined: (a) human contributors using AI tools, (b) autonomous agents, and
   (c) what gets rejected. Each tier has clear, distinct expectations.

4. **CoC explicitly covers autonomous agents** — the Scope section of the Code
   of Conduct includes a dedicated clause stating that autonomous agents are
   subject to the CoC, and that the **human operator** deploying/configuring the
   agent bears responsibility for its behavior. This closes a gap that standard
   CoC templates do not address: who is liable when an agent violates community
   standards.

5. **Self-identification requirement** — all templates (bug report, feature
   request, PR template) include structured fields for agents to self-identify
   (tool/model, operating mode, how the issue was discovered). This mirrors the
   project's own development workflow (Sisyphus agent self-identifies in its
   behavioral instructions) and ensures maintainers can evaluate contributions
   with appropriate context.

6. **Issue/PR templates include agent-originated fields** — both bug report and
   feature request templates have an "Origin (for AI-agent-submitted reports)"
   section asking for agent identity, operating mode, and discovery methodology.
   The PR template has an "Origin" section at the top with provenance
   (human/agent/mixed), tool used, and AGENTS.md compliance flag, plus a
   dedicated subsection for agent-originated PRs (session context, agent
   identity, constitution compliance).

7. **SUPPORT.md addresses agent behavior** — includes an "AI agents and
   automated systems" section with explicit behavioral rules: search before
   posting, self-identify, follow AGENTS.md/CONTRIBUTING.md, no scraping or
   bulk-harvesting.

8. **Security: ML-specific warnings** — SECURITY.md calls out safetensors vs.
   pickle risks and the web server's network exposure, following HuggingFace's
   pattern of ML-specific security guidance.

9. **Issue/PR templates location** — `.github/` directory, matching GitHub's
   convention. Simple `.md` templates (not YAML forms) to avoid over-engineering
   for a single-maintainer project.

10. **No FUNDING.yml** — deferred. Not needed until sponsorship infrastructure
    is desired.

## Consequences

### Positive

- GitHub community profile will show 100% for all checklist items (description,
  README, license, code of conduct, contributing, security, issue template, PR
  template).
- CODE_OF_CONDUCT.md, SECURITY.md, SUPPORT.md, and CONTRIBUTING.md will be
  auto-linked in the repository sidebar for discoverability.
- Issue and PR templates reduce the burden on the maintainer by collecting
  structured information upfront.
- Agent-originated fields in templates provide provenance transparency,
  allowing maintainers to evaluate human vs. agent contributions differently
  when appropriate.
- AGENTS.md is explicitly cross-referenced as the behavioral spec for agents,
  creating a clear chain: CoC → CONTRIBUTING.md → AGENTS.md → Constitution.
- Security policy provides a clear channel for responsible disclosure,
  reducing the risk of uncoordinated public disclosure of vulnerabilities.

### Negative

- Maintenance overhead: these documents need to be kept current (contact
  info, supported versions in SECURITY.md).
- Code of conduct implies a commitment to enforcement. For a single-maintainer
  project this is manageable but should be acknowledged as a responsibility.
- Agent-native fields add length to templates, which may slightly increase
  the barrier for casual human contributors. The tradeoff (provenance
  transparency for an AI-native project) justifies the cost.

### Neutral

- Issue/PR templates may slightly increase barrier to filing, but the tradeoff
  (better quality reports) is worth it for a single maintainer.

## Alternatives Considered

- **Contributor Covenant v1.4** — rejected in favor of v2.1 because v2.1's
  graduated enforcement guidelines provide clearer expectations.
- **Python PSF Code of Conduct** — used by scikit-learn and the Python
  ecosystem. More detailed but requires a Python Software Foundation
  reporting structure. Overkill for a single-maintainer project.
- **Custom code of conduct** — rejected. Standard templates are well-vetted
  and recognized by the community. A custom document would require more
  maintenance and lacks the brand recognition of Contributor Covenant.
- **No AI contribution policy** — rejected. Since anvil uses AI in its own
  development workflow, being silent on AI-generated contributions would
  create ambiguity. The policy sets clear, low-bar expectations.
- **Treating AI contributions as exceptional/special-case** — rejected in
  favor of treating agentic contribution as the normal workflow. A project
  whose maintainer works primarily through AI agents should not frame agentic
  work as exceptional. The "three tiers" structure (human+AI tools / autonomous
  agents / rejected) is more honest and more useful than a single "AI OK"
  policy.
- **No agent self-identification requirement** — rejected. Without provenance
  metadata, a maintainer cannot distinguish between a careful agent-originated
  PR that followed AGENTS.md and a bulk-generated spam PR. Structured
  self-identification fields in templates provide the transparency needed to
  make that judgment.