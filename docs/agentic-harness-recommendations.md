# anvil — Agentic Harness & Onboarding Recommendations Report

**Date**: 2026-06-19
**Scope**: Developer onboarding ease + agentic harness quality
**Reviewer**: Sisyphus
**Method**: Static review of harness config, governance docs, CI, package structure (127 modules), and convention enforcement.

---

## Executive Summary

anvil has one of the **most mature agentic harnesses** I've reviewed: a full Spec Kit lifecycle, a versioned constitution, an Obsidian knowledge vault with controlled vocabulary + graph-health tooling, conventional-commit enforcement, and strict lint/type/docstring gates. The *intent* infrastructure is excellent.

The problem is a **gap between declared discipline and enforced discipline**. The harness *describes* rigorous gates, but they are **not wired into CI**, and several governance documents **contradict each other and the actual code**. For an agent-first codebase, contradictions are uniquely damaging: agents treat governance docs as ground truth, so a conflicting rule produces confidently-wrong work.

The single highest-leverage improvement is not adding more harness — it's **closing the loop between declared rules and machine-enforced reality**.

### Priority snapshot

| # | Issue | Severity | Effort |
|---|-------|----------|--------|
| 1 | No CI runs tests/lint/typecheck on PRs | 🔴 Critical | Low |
| 2 | Constitution forbids `TYPE_CHECKING`; AGENTS.md mandates it; code uses it | 🔴 Critical | Low |
| 3 | `fail_under = 100` coverage gate vs. actual ~41% (and unenforced) | 🔴 Critical | Med |
| 4 | `AnvilWorkbench` "god class" exposes only 1 of ~8 services | 🟠 High | Med |
| 5 | `router.py` is 1958 lines of mixed concerns | 🟠 High | Med |
| 6 | CONTRIBUTING.md (32 lines) too thin; no ARCHITECTURE.md | 🟠 High | Low |
| 7 | Duplicate/colliding ADR numbers | 🟡 Medium | Low |
| 8 | Vault is agent-only; no human entry point | 🟡 Medium | Low |
| 9 | AGENTS.md "Recent Changes" / stale-state drift | 🟡 Medium | Low |

---

## What's Already Excellent (keep / protect)

These are genuine strengths — do not regress them:

- **Spec Kit lifecycle** (`.specify/` + 14 `.opencode/command/*.md`): `specify → clarify → plan → tasks → analyze → implement` with templates and a Constitution Check gate. This is a strong agent workflow.
- **Versioned constitution** (`.specify/memory/constitution.md`, v1.6.0): 10 articles of non-negotiable rules. Clear single source of truth claim.
- **Knowledge vault** (`docs/vault/`): ~100+ notes, 22+ ADRs, ~40 session logs, controlled tag vocabulary (`_meta/tags.md`), note templates, and **graph-health tooling** (`scripts/ci/graph_health/`). The `status/canonical` = human-only rule is a smart guardrail against agents self-certifying.
- **Conventional-commit hook** (`.githooks/commit-msg` via commitizen) + automated semver release.
- **Strict static config** in `pyproject.toml`: `mypy --strict` with `warn_unused_ignores`, ruff with numpy docstring enforcement (`D`), `ignore-without-code`.
- **Layered architecture intent**: Repository → Service → God Class → Routes is a clean, teachable mental model.

The bones are world-class. The recommendations below are about **enforcement, consistency, and human accessibility** — not rebuilding.

---

## 🔴 Critical Findings

### 1. Quality gates are declared but never enforced by CI

**Evidence**: `.github/workflows/` contains only `auto-bump.yml` and `release.yml`. Both trigger on `push: [main]`. **No `pull_request` trigger exists, and nothing runs `make test`, `make lint`, or `make typecheck`.**

The constitution (Art. IV, "Development Workflow & Quality Gates") states: *"Merge gates: `make lint`, `make typecheck` (strict), `make test` (100% coverage). All MUST pass."* CONTRIBUTING.md repeats this. **None of it is machine-enforced.** The "gate" is honor-system + merge review.

**Why this matters for an agent-first repo**: Agents are told gates exist and will catch regressions. They don't. An agent (or human) can merge type errors, lint failures, broken tests, and coverage drops with zero friction. This is almost certainly *why* finding #3 (coverage drift) happened.

**Recommendation**: Add `.github/workflows/ci.yml` triggered on `pull_request` (and `push` to non-main branches) running the exact merge gates the constitution claims:

```yaml
name: CI
on:
  pull_request:
  push:
    branches-ignore: [main]
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: make setup
      - run: make lint
      - run: make typecheck
      - run: make test        # enforces fail_under
      - run: make vault-audit  # 0 errors required
```

Then enable branch protection on `main` requiring this check. **This is the highest-ROI change in the entire report** — it makes every other declared rule actually true.

---

### 2. Governance documents contradict each other and the code (`TYPE_CHECKING`)

This is the most dangerous class of problem for an agent-first codebase: **agents follow the rule they read, and the rules disagree.**

**Evidence**:
- **Constitution** (`.specify/memory/constitution.md`, line 85): *"`TYPE_CHECKING` from `typing` is **forbidden** — circular imports are an architecture problem. Extract shared types into a dedicated module or reorganize layer boundaries."*
- **AGENTS.md** (Principle 10, PEP 563): *"pair PEP 563 with `TYPE_CHECKING` imports: guard the import under `if TYPE_CHECKING:`"* — with a code example **mandating** it.
- **Actual code**: 3 files use `if TYPE_CHECKING:` — `anvil/db/models/corpus.py`, `anvil/db/models/corpus_file.py`, `anvil/services/inference/inference.py`.

So: the constitution bans it, AGENTS.md requires it, and the code does it. The constitution explicitly claims to supersede all other practices and that "root `CONSTITUTION.md` and AGENTS.md … must comply." They don't.

**Impact**: An agent loading the constitution will try to *remove* `TYPE_CHECKING` and "reorganize layer boundaries" — potentially a large, risky refactor — while an agent loading AGENTS.md will *add* it. Both are "following the rules." This is a coin-flip on every relevant edit.

**Recommendation**: **Pick one policy and reconcile all three surfaces in a single ADR + amendment.** The pragmatic choice is to *allow* `TYPE_CHECKING` for genuine cross-module circular-type cases (SQLAlchemy relationship models essentially require it), aligning with AGENTS.md and the existing code. Update constitution line 85, bump constitution version, and record the rationale as an ADR. If the ban is truly intended, then the 3 files are violations that must be refactored — but that should be a deliberate, tracked decision, not silent drift.

> **Broader action**: Add a "governance consistency" check. Even a simple script that greps the constitution, AGENTS.md, and code for known divergent rules (or an `make vault-audit`-style linter over governance docs) would prevent this recurring. Right now there is no mechanism ensuring the three layers agree.

---

### 3. The 100% coverage gate is fiction

**Evidence**:
- `pyproject.toml`: `[tool.coverage.report] fail_under = 100`.
- Constitution Art. IV: *"Unit test coverage MUST be 100% across all layers."*
- `docs/testing-guide.md` (line 220): *"Current coverage: ~41% (improvement needed — tests are minimal; the TDD mandate targets 100%)."*

A `fail_under = 100` gate that has never failed proves the gate isn't running (consistent with finding #1). The codebase advertises a standard it misses by ~59 points.

**Impact**: TDD is a constitutional Article ("TDD Mandatory… 100%"). Agents are instructed to maintain 100%. They either (a) believe it's already met and skip writing tests, or (b) hit an impossible bar and waste cycles. New human contributors face the same confusion the testing-guide itself flags ("coverage debt").

**Recommendation**: Make the target honest and ratcheting:
1. Measure real current coverage in CI (finding #1 enables this).
2. Set `fail_under` to the *current* number (e.g., 41) so it can't regress.
3. Adopt a ratchet: raise `fail_under` over time toward the constitutional goal, or amend Article IV to a realistic phased target ("100% for `anvil/core/`, ≥80% elsewhere, ratcheting up").
4. Update testing-guide.md and the constitution to match whatever is chosen.

A gate that's a lie is worse than no gate — it teaches agents to ignore the gate.

---

## 🟠 High-Priority Findings

### 4. The "God Class" pattern is half-implemented

**Evidence**: `AnvilWorkbench` lives in `anvil/cli.py` (line 40) and exposes **only** `TrainingService` via one property. The constitution (Art. VII) and README state *all* services route through it: *"All services MUST be exposed through a single God Class. Routes, CLI, and tests call the God Class. No shortcuts."* In reality, routes instantiate `TrackingService`, `CorpusService`, etc. directly.

**Impact**: This is the central architectural mental model in the README and constitution. When the documented model doesn't match the code, every new contributor (and agent) is misled about how to wire a new feature. It also means Art. VII is silently violated repo-wide.

**Recommendation**: Decide and align:
- **Option A (honor the constitution)**: Expand `AnvilWorkbench` to expose all services as lazy properties; migrate routes/CLI to use it. Move it out of `cli.py` into its own module (`anvil/workbench.py`) — a god class buried in the CLI entrypoint is itself surprising.
- **Option B (amend the constitution)**: If direct service instantiation is acceptable, soften Art. VII to match reality.

Either way, **document the chosen pattern with a concrete "how to add a service" example** in CONTRIBUTING/ARCHITECTURE.

### 5. `router.py` (1958 lines) is the worst onboarding/agent friction point

**Evidence**: `anvil/api/v1/router.py` is 1958 lines — nearly 2× the next-largest file — mixing route aggregation, page rendering, health checks, service management, and learning content. Adjacent route modules are also monoliths: `datasets.py` (1269), `experiments.py` (803), `training.py` (721); plus `services/tracking/tracking.py` (1203), `services/inference/inference.py` (907).

**Impact**: For agents, large files are token-expensive to read and edit safely, and increase the blast radius of every change. The constitution's "one class per file" and Article X (domain decomposition) discipline is well-applied in `services/` but **not** in `api/v1/`. This is an internal inconsistency in how rigorously the rules are applied.

**Recommendation**: Make `router.py` a thin aggregator that only `include_router`s sub-routers. Extract page-rendering, health, and ops routes into dedicated modules. Apply the same Article X cohesion test to `api/v1/` that's already applied to `services/`. Track this as a structural-only PR (per Constitution §10.9: moves + import rewrites, zero behavioral delta).

### 6. Human onboarding docs are thin; no architecture narrative

**Evidence**: `CONTRIBUTING.md` is 32 lines (setup + commands + commit format only). There is no `ARCHITECTURE.md`. The README has an ASCII tree but no data-flow narrative. The vault (rich architectural content) is structured *for agents/Obsidian*, with no human "start here."

**Impact**: A new *human* developer has README + a 32-line CONTRIBUTING + a 277-line testing-guide, then a wall of 127 modules. The deep "why" lives in ADRs they won't discover.

**Recommendation**:
- Add `ARCHITECTURE.md`: narrate Repository → Service → God Class → Routes with a data-flow diagram and a worked "add a new endpoint" example.
- Expand `CONTRIBUTING.md` with: a service map, "where do I put X" decision guide, the constitution's key articles in brief, and links into the vault's canonical ADRs.
- Add a human-readable ADR index (see #8).

---

## 🟡 Medium-Priority Findings

### 7. Colliding / duplicate ADR numbers
Three ADR numbers collide (verified): **008** (`ADR-008-automated-semver-release` + `ADR-023-data-page-tabbed-layout`), **010** (`ADR-010-disable-local-mlflow-server` + `ADR-025-numpy-docstring-enforcement`), and **016** (`ADR-024-auto-db-migration` + `ADR-016-mlflow-primary-lineage`). These were resolved by renumbering the later duplicates to ADR-023, ADR-025, and ADR-024 respectively. Duplicate identifiers break the "single decision per number" contract and make wikilinks/citations ambiguous.
**Recommendation**: Renumber to unique sequential IDs; add an ADR-number-uniqueness check to `vault_audit.py`.

### 8. The vault has no human-facing index of decisions
`docs/vault/index.md` is an Obsidian navigation hub, but there's no flat, readable list of "what was decided and why" for someone not in Obsidian.
**Recommendation**: Auto-generate `docs/vault/Decisions/README.md` (ADR title + status + one-line summary) as part of `make vault-audit`. Link it from CONTRIBUTING/ARCHITECTURE.

### 9. AGENTS.md state-tracking drift
AGENTS.md carries a long "Active Technologies" / "Recent Changes" log with feature-branch slugs (some duplicated, e.g., multiple "ADR-016" / "005-…" entries) and a manually-maintained "Last updated" date. Manually-curated changelogs in agent-context files drift and bloat the agent's context window.
**Recommendation**: Trim AGENTS.md to durable rules; move the per-feature changelog to `CHANGELOG.md` (already automated) or a generated section. Keep the agent-facing file lean and timeless.

---

## Cross-Cutting Theme: Declared vs. Enforced

The recurring pattern across the critical findings is a **declaration/enforcement gap**:

| Declared | Reality |
|----------|---------|
| "Merge gates: lint, typecheck, test, 100% coverage all MUST pass" | No CI runs them |
| "`TYPE_CHECKING` is forbidden" | AGENTS.md mandates it; code uses it |
| "100% coverage" | ~41%, unmeasured in CI |
| "All services through the God Class" | 1 of ~8 services |
| "One class per file / domain decomposition" | Honored in `services/`, not `api/v1/` |

For an agent-first codebase this gap is the core risk: **agents are literalists.** They cannot tell which rules are real. The fix is consistently to **make the machine the source of enforcement**, and **make the docs agree with the machine.**

### Suggested sequence (fastest path to a trustworthy harness)

1. **Add CI** (finding #1) — turns every declared gate real. *Low effort, unblocks everything.*
2. **Set honest `fail_under`** (finding #3) — so CI passes today and ratchets up.
3. **Reconcile `TYPE_CHECKING`** via ADR + amendment (finding #2) — removes the worst agent coin-flip.
4. **Decide the God Class policy** and document it (finding #4).
5. **Author ARCHITECTURE.md + expand CONTRIBUTING.md** (finding #6).
6. **Split `router.py`** as a structural-only PR (finding #5).
7. **Housekeep**: ADR numbering + uniqueness check, vault decision index, trim AGENTS.md (findings #7–9).

---

## Appendix: Evidence Index

- CI: `.github/workflows/{auto-bump,release}.yml` — no `pull_request` trigger, no test/lint/typecheck steps.
- Constitution: `.specify/memory/constitution.md` (v1.6.0) — Art. IV (TDD/coverage), Art. VII (God Class), line 85 (`TYPE_CHECKING` ban), Art. X (decomposition).
- AGENTS.md: Principle 10 (mandates `TYPE_CHECKING` with PEP 563).
- `TYPE_CHECKING` usage: `anvil/db/models/corpus.py:13`, `anvil/db/models/corpus_file.py:11`, `anvil/services/inference/inference.py:13`.
- Coverage: `pyproject.toml` `fail_under = 100`; `docs/testing-guide.md:220` "~41%".
- God class: `anvil/cli.py:40` (`AnvilWorkbench`, exposes only `TrainingService`).
- Large files: `anvil/api/v1/router.py` (1958), `datasets.py` (1269), `services/tracking/tracking.py` (1203), `services/inference/inference.py` (907), `cli.py` (827).
- Harness: `.specify/` (Spec Kit), `.opencode/command/` (14 commands), `docs/vault/` (~100 notes, 22+ ADRs), `scripts/ci/graph_health/`, `.githooks/commit-msg`.
