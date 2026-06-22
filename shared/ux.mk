# UX checks (Spec Kit + OpenCode + OMO repo).
#   make ux-lint    deterministic mechanical-S4 gate (zero deps, no network)
#   make ux-review  optional AI full-ruleset pass (needs UX_API_KEY; routes via your fleet)
#
# FILES defaults to changed UI/template files vs origin/main; override explicitly:
#   FILES="templates/forge/dashboard.html static/forge.css" make ux-review

EXT   := html|htm|jinja|jinja2|j2|css|scss|sass|less|js|jsx|ts|tsx|vue|svelte|py
FILES ?= $(shell git diff --name-only --diff-filter=ACMR origin/main... 2>/dev/null | grep -E '\.($(EXT))$$')

.PHONY: ux-lint ux-review

ux-lint: ## Run deterministic UX lint (mechanical S4 gate)
	@python scripts/ci/ux_lint.py $(FILES)

ux-review: ## Run AI UX review (requires UX_API_KEY; set UX_API_KEY env var)
	@python scripts/ci/ux_review.py $(FILES)