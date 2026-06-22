# Research: UX Rules Integration

## Research Task 1: scripts/ci/ Convention

**Decision**: Place `ux_lint.py` and `ux_review.py` in `scripts/ci/` as documented convention exceptions.

**Rationale**: The `scripts/README.md` states "Thin wrappers only — scripts delegate to `anvil-vault`." However, `ux_lint.py` and `ux_review.py` are intentionally self-contained tools requiring zero pip dependencies and working without the `anvil` package installed. This is by design — the linter must run in CI environments and the review script must work as a standalone CLI tool. The scripts follow all other conventions (stdlib-only, snake_case, `if __name__ == "__main__":` pattern). Document the exception in the quickstart.

**Alternatives considered**:
- Refactor into thin wrappers + `anvil/services/` package logic — adds unnecessary complexity and pip dependency for CI use.
- Place elsewhere (e.g., `ci/` at repo root) — creates a new top-level directory, discarded via Q2 clarification.

## Research Task 2: Makefile Include Syntax

**Decision**: Use `include shared/ux.mk` in the root Makefile.

**Rationale**: The root `Makefile` uses plain `include shared/filename.mk` (no hyphen, no leading `./`). Targets in shared includes follow `target: ## description` pattern with `.PHONY: target` at end of file. `shared/ux.mk` will follow this exactly.

**Reference pattern** from `shared/helper.mk`:
```makefile
help: ## Show all documented commands
	@echo "..."
.PHONY: help
```

## Research Task 3: OpenCode Skill Discovery

**Decision**: Place SKILL.md files — no config registration needed.

**Rationale**: OpenCode discovers skills via filesystem (`./opencode/skills/<name>/SKILL.md`). No registration in `opencode.json` or other config is required. The existing `.opencode/` directory has no skills subdirectory; it will be created during placement.