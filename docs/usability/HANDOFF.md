# HANDOFF — UX rules + gate → Anvil (Spec Kit + OpenCode + OMO)

**For:** the implementing agent (Sisyphus to delegate; review work suits a
read-only/review agent, placement suits a build agent).
**Goal:** subsume the UX review/generation ruleset and its deterministic gate
into the host repo's existing Spec Kit + OpenCode + OMO stack, repo-internal, no
network fetch.
**Status:** ✅ All artifacts placed, framework wired, OQ decisions recorded.
Remaining runtime verification (T007, T009) deferred to OMO session —
on-disk artifacts verified. Smoke-tested and passing.

---

## Decisions & discovery

Resolved across design; the discovery items (D5–D7) come from cross-referencing
official docs this iteration.

- **D1 — Ruleset provenance.** Behavioral core forked from Vercel Web Interface
  Guidelines (MIT); framework-/brand-specific rules dropped; universal
  a11y/focus/forms/motion/i18n kept. Owned sections added: Server-render (Jinja),
  Streaming (SSE), Terminal aesthetic (CRT/TUI). Severity/dedup/injection-
  quarantine model from Rune.
- **D2 — Two axes.** Severity (S4–S1, how bad) × Enforceability
  (`lint` / unmarked=ai-review / `test`=runtime-only). Tagged inline in the rules.
- **D3 — Two-tier checking.** Deterministic `ci/ux_lint.py` (mechanical S4 subset,
  regex, zero-dep) is the gate; optional `ci/ux_review.py` (model, full ruleset)
  is the deep pass.
- **D4 — Repo-internal.** No fetch. Ruleset at `docs/ux-rules.md`; skills and AI
  review resolve it locally.
- **D5 — OpenCode skills (discovery).** Loaded from `.opencode/skills/*/SKILL.md`
  (plural default), plus `.claude/skills/`, `.agents/skills/`, walking to the git
  worktree. SKILL.md needs YAML frontmatter; only recognized fields read, unknown
  ignored → `name`+`description` suffice, our shims drop in natively.
- **D6 — OMO is an OpenCode plugin (discovery).** Config `.opencode/oh-my-opencode.json`;
  skill priority **project > user > opencode > builtin/plugin** → our project
  skills win; the 11-agent fleet uses them via the `skill` tool. No OMO-specific
  path. OMO tooling also scans the `Makefile`.
- **D7 — Spec Kit governance (discovery).** `/speckit.analyze` treats
  `.specify/memory/constitution.md` MUST principles as CRITICAL gates; but
  `specify init --force` overwrites `.specify/memory/`. → keep the ruleset in
  `docs/`, reference it FROM the constitution to get SDD gating without clobber
  risk.
- **D8 — Gate via Make targets now.** `make ux-lint` / `make ux-review`.
  Pre-commit deferred (owner decision). CI wiring = call `make ux-lint` when ready.
- **D9 — AI review routed through the fleet.** Either an OMO agent's assigned
  model (agent route) or `UX_MODEL_BASE_URL`→your router (script route). No
  bespoke provider config.
- **D10 — Injection quarantine.** Operating contract: files under review are
  untrusted data; embedded directives are surfaced as `[S4] security`, never
  obeyed. Mirrors the repo-rule-overrides-skill-default posture OMO uses in its
  own AGENTS.md.

**Fixes applied this iteration:** CSRF severity contradiction resolved (Forms +
Server-render both S4); comment-blanking added to the linter (mentions in
comments no longer false-positive; in-comment suppression annotations still
read); enforceability axis added; i18n reframed for server-side, idempotency-key
marked backend/out-of-scope; Anti-patterns labeled a derived view.

---

## Artifacts

| File (bundle) | Target path in repo | Purpose | Status |
|---|---|---|---|
| `docs/ux-rules.md` | `docs/ux-rules.md` | Single source of truth | ready |
| `.opencode/skills/ux-review/SKILL.md` | same | Review projection (audit→findings) | ready |
| `.opencode/skills/ux-generate/SKILL.md` | same | Generate projection | ready |
| `ci/ux_lint.py` | `ci/ux_lint.py` | Deterministic S4 gate, zero-dep | tested |
| `ci/ux_review.py` | `ci/ux_review.py` | Optional AI full review | py-compiled |
| `Makefile` | merge into repo `Makefile` | `ux-lint` / `ux-review` targets | ready |
| `INTEGRATION.md` | `docs/` (reference) | Wiring + rebind surface | ready |

---

## Tasks (completed 2026-06-21)

IDs are dependency-ordered; `[P]` = parallelizable with siblings. Exact paths given.
Status: ✅ done · ❓ runtime-verify · ❌ decided-no-action

- **T001** ✅ Place `docs/ux-rules.md` at repo root `docs/`.
- **T002 [P]** ✅ Place skills: `.opencode/skills/ux-review/SKILL.md`,
  `.opencode/skills/ux-generate/SKILL.md`.
- **T003 [P]** ✅ Place scripts: rebound to `scripts/ci/ux_lint.py`,
  `scripts/ci/ux_review.py` (repo convention). Makefile paths updated to match.
- **T004 [P]** ✅ Merge the two `Makefile` targets (`ux-lint`, `ux-review`) into
  `shared/ux.mk` (included by `Makefile`). Fix applied: bare `python` → `$(PYTHON)`.
- **T005** ✅ Wire Spec Kit governance: UI-compliance MUST principle added to
  `.specify/memory/constitution.md` (refs `docs/ux-rules.md`).
- **T006** ✅ Decided: skill-only (on-demand). No `opencode.json` instructions needed.
- **T007** ❓ Skills confirmed on disk at `.opencode/skills/ux-*/SKILL.md` with
  valid YAML frontmatter. Full load-verification requires a running OpenCode/OMO
  session (`skill` tool in this env does not discover project-level skills).
- **T008** ✅ Smoke-tested: `make ux-lint` on `concept.html` (has `|safe`) →
  `GATE: FAIL [S4:1]` ✓. Clean file (`README.md`) → `GATE: PASS` ✓.
  `ux-review` not tested (needs `UX_API_KEY`).
- **T009** ❓ Skills well-formed and at correct paths. Full fleet-usage
  confirmation deferred to a running OMO session with `ux-review`/`ux-generate`
  loaded at project priority.
- **T010** ✅ Applied: scripts → `scripts/ci/`, Makefile → `shared/ux.mk`.
  Identifiers kept generic (`UX_*`, `ux-lint:allow`, `[S<n>]`, skill names).
- **T011** ✅ Decided: leave local. No CI wiring for `ux-lint` at this time.

---

## Open questions — resolved 2026-06-21

- **OQ1 — Ruleset home.** `docs/ux-rules.md` — kept as-is. ✅
- **OQ2 — Generation enforcement.** Skill-only (on-demand, lean). ✅ Decided.
- **OQ3 — Spec Kit depth.** Full: constitution principle (done in T005) + UX
  checklist section added to `.specify/templates/checklist-template.md` +
  `make ux-lint` verification tasks added to `.specify/templates/tasks-template.md`. ✅
- **OQ4 — CI now or later.** Leave local. No CI wiring. ✅ Decided.
- **OQ5 — Review model ownership.** Default / unopinionated — whichever agent
  invokes the skill. ✅ Decided.
- **OQ6 — SSE per-chunk gate gap.** Accept as-is (AI-review only). No runtime
  gate investment. ✅ Decided.
- **OQ7 — Rebind.** Keep generic identifiers (`UX_*`, `ux-lint:allow`, `[S<n>]`,
  skill names). Scripts rebound to `scripts/ci/` (repo convention). ✅
- **OQ8 — Spec Kit presence.** Yes, `.specify/` exists. Constitution principle
  merged into existing file (no `--force` clobber). ✅

---

## Acceptance criteria — status

| Criterion | Status |
|-----------|--------|
| Skills load at **project** priority; `skill` tool lists both. | ❓ On-disk at correct paths — runtime verify with OMO |
| `make ux-lint` fails on a seeded mechanical S4 and passes a clean file. | ✅ Passes both (FAIL on `\|safe`, PASS on clean) |
| `.specify/memory/constitution.md` references `docs/ux-rules.md` | ✅ Present |
| UX checklist auto-injected for UI features via `/speckit.checklist` | ✅ Checklist template updated |
| `make ux-lint` verification task auto-injected via `/speckit.tasks` | ✅ Tasks template updated |
| `ux-generate` engages during UI edits; `ux-review` runs on demand via the fleet. | ❓ Skills well-formed — runtime verify with OMO |
| All OQ decisions recorded, rebind applied if chosen. | ✅ All decisions recorded above |

---

## References (official)

- Spec Kit — https://github.com/github/spec-kit · upgrade: https://github.com/github/spec-kit/blob/main/docs/upgrade.md
- OpenCode skills — https://opencode.ai/docs/skills · config — https://opencode.ai/docs/config · rules — https://opencode.ai/docs/rules
- OMO — https://github.com/code-yeongyu/oh-my-openagent (docs/reference/features.md)
