# Staffing Plan — Anvil (v1)

**Author**: Board
**Status**: Draft v1
**Date**: 2026-07-05
**Spec**: `specs/065-paperclip-bootstrap/spec.md`

---

## 1. Current State

### Product
**anvil** is a pip-installable Python package for training and experimenting with LLMs from scratch. It pairs a zero-dependency training engine (RoPE, SwiGLU MLP, RMSNorm) with a FastAPI web server, MLflow experiment tracking, and an iOS-modern web UI.

### Codebase Maturity

| Metric | Value | Verification note |
|--------|-------|-------------------|
| Source LOC | ~15,000+ (`anvil/`) | Core engine, services, API, storage, supervisor |
| Test LOC | ~2,600+ (49 files) | Unit + e2e tests |
| Test coverage | ~41% (`fail_under` in pyproject.toml) | TDD mandate targets 100% |
| Release maturity | v0.13.0 | Production-grade build, Docker, CI/CD |
| Development cadence | 60+ specs, active development | Spec Kit workflow (specify → plan → implement) |
| Quality gates | `make pr-ready`: format → lint → typecheck → ux-lint → vault-audit → constitution-check → test | All must pass before merge |

### Known Debt

- **Coverage gap**: ~41% coverage is below the aspirational 100% target. TDD mandate in effect.
- **Spec backlog**: 60+ specs exist; some may be stale or superseded.
- **No paperclip agent orchestration yet**: This plan is the first step.

### Current Team (Paperclip)

| Agent ID | Role | Status |
|----------|------|--------|
| *(to be created by anvil-seed.sh)* | CEO | Pending |
| *(to be created by anvil-seed.sh)* | Platform Engineer | Pending |
| *(to be created by anvil-seed.sh)* | UX Engineer | Pending |

---

## 2. Proposed Team Structure

### Size: 3 agents (CEO + Platform Engineer + UX Engineer)

```
Human operator (board)
└── CEO — routing hub + prioritization proposals
    ├── Platform Engineer — Core engine, API, training, ops
    └── UX Engineer — Web UI, design system, templates
```

### Decomposition by work shape

| Work shape | Owner | Rationale |
|------------|-------|-----------|
| Routing, inbox triage, spec sequencing, board reporting | **CEO** | At n=3 a dedicated coordinator is overhead; CEO absorbs routing until agent count ≥ 4 |
| Core engine, training pipeline, API layer, storage, ops/infra, datasets | **Platform Engineer** | Backend/infra work — Python, FastAPI, SQLAlchemy, Docker, MLflow |
| Web UI, design system, CSS tokens, templates, UX rules, accessibility | **UX Engineer** | Frontend/design work — Jinja2, CSS, design tokens, a11y |
| Architecture/code review | **Mechanical gates + on-demand critic** | `make pr-ready` + `make lint` + `make typecheck` + multi-agent review workflow |
| Constitution, merges, version bumps, epic priority calls | **Human only** | Reserved powers (§4) |

### Roles not created, and why

- **ML Engineer / Data Scientist** — their work (training, datasets, experiments) is a subset of Platform Engineer's domain. If volume justifies specialization later, add at that point.
- **QA / Fidelity Reviewer** — anvil's maturity (0.13.0, CI/CD, test suite) means quality gates are mechanical, not agent-driven. Conjure needed this because it was pre-implementation.
- **DevOps / SRE** — Docker/CI/CD work is part of Platform Engineer's domain. Specialize when multi-service complexity demands it.

---

## 3. Charters and Guardrails (per agent, before first heartbeat)

### File structure (in each agent's managed Paperclip `AGENTS.md`, assembled from)
- **SOUL** — identity, values, voice (rare changes)
- **CHARTER** — mission, authority, boundaries, escalation (quarterly)
- **INTENT** — current priorities and kill-switches (weekly, CEO-maintained)

### Every charter MUST contain

1. **Authority** with explicit out-of-scope list
2. **Reserved powers carve-out** (§4 — verbatim in every charter)
3. **Machine-checkable behavioral invariants**, e.g. for the Platform Engineer:
   - Every PR references a spec task ID (T-x.y.z)
   - Every feature commit is preceded by a failing-test commit (TDD mandate per Constitution Article IV)
   - `make pr-ready` passes before any PR is opened
   - No PR touches `.specify/memory/constitution.md`
4. **Escalation path**, e.g. Platform Engineer: *2+ failed implementation attempts on a task → STOP, post state to the issue, summon CEO review; ambiguity in a spec → route to CEO, do not guess.*
5. **Structured-artifact handoffs only** — work moves via specs, tasks.md, PRs, and issue comments. Never free-form chat between agents (role-drift risk).

### Budgets (Paperclip-enforced, not decorative)

| Agent | Monthly ceiling |
|-------|----------------|
| CEO | $20 |
| Platform Engineer | $30 |
| UX Engineer | $25 |
| **Company hard cap** | **$75** |

Heartbeats start disabled; enable deliberately, one agent at a time.

---

## 4. Reserved Powers (Human-Only — In Every Charter)

1. Constitution amendments
2. Version bumps and releases
3. Merge rights to `main`
4. Hiring approvals (`requireBoardApprovalForNewAgents` stays on)
5. Budget changes

Agents may *propose* any of these via the Approvals queue; none may *execute* them.

---

## 5. Sequencing

### Phase 0 — Operationalize Paperclip
1. Run `bash docs/anvil-seed.sh` to create the Anvil company in Paperclip
2. Review the seeded company at http://localhost:3100
3. Enable CEO heartbeat → CEO reviews spec backlog and creates tickets
4. Enable Platform Engineer and UX Engineer heartbeats → engineers pick up tickets
5. Human reviews agent output, merges PRs

### Phase 1 — Spec Backlog Work
- Engineers work through the spec backlog in priority order
- CEO routes tickets, maintains INTENT file, reports weekly to board
- Human merges are the gate for all PRs

### Phase 2 — Ongoing Development
- Standard Spec Kit workflow: specify → plan → tasks → implement
- Agents work independently on their domains
- CEO coordinates cross-domain work (e.g., API changes that affect UI)

---

## 6. Success and Kill Criteria

**Success (measured over Phase 1):**
- S1: At least 5 specs progress from draft → implemented per month
- S2: Total human review time < 4 hours per week
- S3: Zero constitution violations reaching a PR
- S4: Spend within budget ceilings

**Kill (any one triggers rollback to solo-human workflow + retrospective):**
- K1: Human review time > 8 hours in a single week — the org is net negative on labor
- K2: Hard budget pause hit ($75) before Phase 1 completes
- K3: An agent executes a reserved power
- K4: 3+ critic-review cycles on the same task without convergence

---

## 7. Concrete Next Actions

| # | Action | Owner |
|---|--------|-------|
| 1 | Run `bash docs/anvil-seed.sh` to bootstrap the Anvil company | Operator |
| 2 | Verify company, goals, projects, agents, and tickets at http://localhost:3100 | Operator |
| 3 | Enable CEO heartbeat; CEO reviews and prioritizes spec backlog | Operator |
| 4 | Enable Platform Engineer and UX Engineer heartbeats | Operator |
| 5 | Load charters into managed AGENTS.md for each agent (SOUL/CHARTER/INTENT) | CEO |
| 6 | Monitor agent output for first week; adjust budgets and priorities as needed | Operator + CEO |

---

## 8. Risks

- **CEO as routing hub is a single point of drift** — persona self-consistency degrades after extended turns. Mitigation: INTENT file refreshed weekly; structured-artifact handoffs keep routing decisions out of long chat threads.
- **Coverage claim is aspirational** — 41% coverage means untested code exists. TDD mandate is the ratchet; agents must follow it.
- **Spec backlog quality unknown** — 60+ specs exist; some may be stale. CEO should audit and consolidate before assigning.
- **Paperclip seed idempotency** — re-running `anvil-seed.sh` duplicates goals/projects/agents. All provisioning changes go through CLI/UI, never re-seeding.