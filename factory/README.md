# `factory/` — the Gas City agent pack that builds anvil

This directory is the **pack**: the agents and formulas a local Gas City factory uses to execute
tasks from `docs/vault/Specs/*/tasks.md`.

It lives at the repo root, **deliberately not under `anvil/`** — see [Why not under
`anvil/`](#why-not-under-anvil).

## Layout

```
factory/
├── pack.toml                            pack identity; declares the always-on manager
├── agents/<name>/agent.toml             how each agent runs
├── agents/<name>/prompt.template.md     what each agent knows
└── formulas/anvil-*.formula.toml        the order they work in, one per task type
```

Agents are declared **by directory** (schema 2). There are intentionally no `[[agent]]` tables in
`pack.toml`: an inline table silently shadows the matching `agents/<name>/agent.toml`, and
`gc doctor` flags it as a legacy declaration.

## The agents

| Agent | Mode | Role |
| --- | --- | --- |
| `manager` | always-on | The only agent a human talks to. Routes work, picks the formula from `task_type`, reports. Writes no code, merges nothing. |
| `planner` | pool | Turns a task row into written acceptance; classifies `task_type`; flags migrations. |
| `builder` | pool | The only agent that changes files. Commits, opens the PR. |
| `architect` | pool | The gate: mechanical checks, then exactly four judgment calls. |
| `scribe` | pool | Vault enrichment, `make vault-audit`, closes the bead. |

**Every agent is capped at `max_active_sessions = 1`.** All agents share the single rig checkout; two
agents writing branches in one working tree collide. Raise this only after giving each its own git
worktree.

## The formulas — one per task type

Gas City formulas cannot express conditional step-skipping, so branching is per-formula and the
manager selects with `--on`.

| `task_type` | Formula | Steps |
| --- | --- | --- |
| `refactor` | `anvil-refactor` | plan → build → gate → scribe |
| `feature` | `anvil-feature` | plan → build (Red→Green→Refactor commits) → gate → scribe |
| `investigation` | `anvil-investigation` | plan → investigate → scribe |
| `human_decision` | `anvil-human-decision` | plan → blocked |

**One builder step per formula, never two.** Consecutive steps owned by the same agent cannot hand
off — see below — so all builder work lives in a single step. For `anvil-feature` that step still
produces three separate, ordered commits (`test:` → `feat:` → `refactor:`); Article IV constrains
commit order, not step count, and the architect verifies ordering from `git log`.

`anvil-refactor` is the workhorse. Only ~73 of anvil's 474 open task rows carry TDD markers, so most
work has no Red phase to write — and fabricating one to satisfy a pipeline would violate Article XI.

## Step handoff: release the assignee before routing

Every routing site in a formula **must** clear the assignee before slinging onward:

```bash
bd update {{issue}} --assignee ""
gc sling {{rig}}/factory.<next> {{issue}}
gc runtime drain-ack
```

This is not cosmetic. `gc sling` assigns the bead to the target agent's session **only when the bead
is unassigned**, and it is idempotent on an already-routed bead. So if an agent routes onward while
still holding the assignment, the result is:

```
warning: bead av-pmh routed to "anvil/factory.builder"
         but assigned to "factory__planner-af-yxww"
```

The next pool agent spawns, finds nothing under
`bd list --status=open --assignee="$GC_SESSION_NAME"`, and idles. **The pipeline stalls silently
after the first step** — no error, just a bead that never advances.

Found the hard way during the first live run; see E17 in the onboarding plan. Order matters: clear
*then* sling. Clearing after the sling is too late, because the sling has already been skipped as
idempotent.

### Corollary: never give two consecutive steps to the same agent

The same idempotency defeats a builder→builder handoff entirely. If step *n* and step *n+1* are both
owned by `builder`, routing onward does not change `gc.routed_to`, so the sling is skipped, the
assignee is never set, and **the run stalls with no error** — the commit from step *n* is left
unpushed on a local branch.

Found on the second live run (E18). Both `anvil-refactor` and `anvil-feature` were restructured to a
single `build` step for this reason.

## Two rules the prompts encode that are easy to get wrong

**The gate must not run `make pr-ready`.** `pr-ready` begins with `make format`, which rewrites files.
Running it as a verification step leaves unstaged reformatting belonging to no commit. The architect
runs the non-mutating subset instead:

```bash
make lint && make typecheck && make vault-audit && make constitution-check && make test
```

`make lint` already contains `black --check` and `isort --check`, so formatting is verified without
being changed.

**The builder must `make format` before `git add`.** The pre-commit hook also runs `make format`; if
files are staged unformatted, the hook reformats them *after* staging and the commit captures the
wrong content. Formatting first makes the hook's pass a no-op.

## Mechanical vs judgment

anvil automates far more than most projects, so the architect's judgment scope is deliberately tiny.
Already covered by `make constitution-check` / `make lint` / `make typecheck` / `make vault-audit`:
layer discipline, `__init__.py` ownership, relative-imports-only, import placement, package nesting,
one-class-per-file, `py.typed`, zero-dependency core, ADR presence, mypy strictness, docstrings,
Pydantic-over-dataclass, bandit, semgrep, and vault conventions.

The architect judges only what tooling cannot:

1. **TDD ordering** (features only) — `test:` → `feat:` → `refactor:`, with captured Red output
2. **Enums over magic strings** — the highest-value check; invisible to tooling
3. **Simplicity First / YAGNI** — speculative abstraction, unused knobs, unrecorded complexity
4. **Domain placement** — types in the right bounded context

Deliberately **not** checked (no mechanical check exists, and not worth LLM tokens): "Python over
Bash" for scripts, and solid `#` comment separators.

## Editing this pack — the re-pin loop

The pack is imported from inside a git worktree, so `gc import add` pins it to a **commit SHA**. A
prompt edit is not live until it is committed and re-pinned:

```bash
# 1. edit a prompt or formula
make format && git add -A
git commit -m "chore(factory): <what changed>"   # hook runs the full gate, ~2 min

# 2. re-pin the city's import to the new commit
cd /path/to/anvil-factory
gc import add --rig anvil /path/to/anvil/factory
gc reload

# 3. sanity check
gc prime manager
```

That ~2 minute gate per edit is the accepted cost of versioning agent instructions alongside the code
they change: prompt changes get PR review, and any bad PR can be traced to the exact prompt SHA that
produced it.

## Why not under `anvil/`

Three separate mechanisms break if this directory moves inside the Python package:

| If placed under `anvil/` | Consequence |
| --- | --- |
| `release.yml` push filter is `paths: ['anvil/**', 'pyproject.toml', 'uv.lock']` | every prompt edit would cut a **version bump, tag, and GitHub release** |
| `[tool.setuptools.packages.find] include = ["anvil*"]` | the pack would be **shipped inside the wheel** |
| `anvil-vault check-init-py` / `check-nesting` | pack directories would be judged against the `__init__.py` ownership policy |

At the repo root, none apply.

## Verifying the factory actually works

`gc status` reporting `0/N agents running` is **normal** with no work queued — pool agents declare
`min_active_sessions = 0`. A session marked `active`/`awake` in the registry is **not** proof anything
is running.

The only reliable test is to sling a bead and look for a session carrying a provider `session_key`:

```bash
gc sling anvil/factory.planner <bead-id> --on anvil-refactor
gc session list        # expect a session with a real session_key
```
