---
title: Pre-commit and pr-ready Tooling Pattern
type: discovery
status: draft
source: agent
tags:
  - type/discovery
  - domain/tooling
  - status/draft
aliases:
  - Pre-commit and pr-ready Tooling Pattern
code-refs:
  - .githooks/pre-commit
  - .githooks/commit-msg
  - shared/python.mk
  - Makefile
session: 2026-06-21-linting-testing-hooks-tooling
created: '2026-06-21'
updated: '2026-06-21'
---
The pre-commit hook and `make pr-ready` target form a two-tier quality gate system: the hook prevents non-conformant code from entering the repo on every commit, while `pr-ready` gives developers an explicit pre-PR validation command that matches what CI runs.

**Key observations:**

1. **`make format` was a stub** — The `format` target was declared `.PHONY` in `shared/python.mk` but had no recipe. When `make format` was called (documented in README, AGENTS.md, and the help system), it silently did nothing. Added recipe: `black . && isort .`.

2. **`make typecheck` was a stub** — Same issue. The CI `typecheck` job called `make typecheck` which was a no-op. Added recipe: `mypy anvil/`.

3. **pre-commit must be simple to be tolerable** — Running `make pr-ready` (three-step: format → lint → typecheck) in a pre-commit hook is reasonable on a project this size because:
   - `black` + `isort` are near-instant on incremental changes
   - `ruff` C-extensions run in milliseconds
   - `pylint` + `mypy` are the slowest links (~5-10s combined)
   - Total wall time on this codebase (~100 Python files): ~10-15s.
   - Developers always have `git commit --no-verify` as an escape hatch.

4. **`setup-hooks` installs both hooks** — The existing `make setup-hooks` set `core.hooksPath = .githooks/` but only documented the `commit-msg` hook. Updated to describe both `commit-msg` (conventional commits) and `pre-commit` (format + lint + typecheck).

5. **`.githooks/` vs `pre-commit` framework** — This project uses bare `.githooks/` scripts with `core.hooksPath`, not the Python `pre-commit` framework. This keeps dependencies minimal (no `.pre-commit-config.yaml`, no hook runtime) and consistent with the existing `commit-msg` hook pattern. The trade-off is no per-hook caching or parallel execution — each hook is a single shell script.

## References
- [[Discoveries/Discoveries|Discoveries]]

- `.githooks/pre-commit` — pre-commit hook script
- `.githooks/commit-msg` — conventional commit hook script
- `shared/python.mk` — `format`, `typecheck`, `lint` recipe definitions
- `Makefile` — `setup-hooks`, `pr-ready` targets
- `docs/vault/Reference/linting-and-testing-tooling.md` — companion reference
