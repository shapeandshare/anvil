---
title: 025 UX Rules Integration - quickstart
type: quickstart
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/025 UX Rules Integration/
related:
  - '[[025 UX Rules Integration]]'
created: ~
updated: ~
---
# Quickstart: UX Rules Integration

## What this is

This feature integrates a UX ruleset, deterministic linter, and AI review system into the repo. Developers run `make ux-lint` for fast mechanical checks; OMO agents use `ux-generate` and `ux-review` skills for compliant-by-construction generation and deep analysis.

## Integration steps

### Step 1: Place the ruleset

```bash
cp docs/usability/ux-rules.md docs/ux-rules.md
```

### Step 2: Place OpenCode skills

```bash
mkdir -p .opencode/skills/ux-review .opencode/skills/ux-generate
cp docs/usability/SKILL.md .opencode/skills/ux-review/SKILL.md
# Create ux-generate/SKILL.md from the HANDOFF's generate projection
```

### Step 3: Place CI scripts

```bash
cp docs/usability/ux_lint.py scripts/ci/ux_lint.py
cp docs/usability/ux_review.py scripts/ci/ux_review.py
```

> **Note**: These scripts break the "thin wrappers only" convention of `scripts/` — they are intentionally self-contained tools requiring zero pip dependencies. This exception is documented and by design.

### Step 4: Add Makefile include

Create `shared/ux.mk`:

```makefile
EXT   := html|htm|jinja|jinja2|j2|css|scss|sass|less|js|jsx|ts|tsx|vue|svelte|py
FILES ?= $(shell git diff --name-only --diff-filter=ACMR origin/main... 2>/dev/null | grep -E '\.($(EXT))$$')

.PHONY: ux-lint ux-review

ux-lint: ## Run deterministic UX lint (mechanical S4 gate)
	@python scripts/ci/ux_lint.py $(FILES)

ux-review: ## Run AI UX review (requires UX_API_KEY)
	@python scripts/ci/ux_review.py $(FILES)
```

Add to root `Makefile` alongside existing includes:

```makefile
include shared/ux.mk
```

### Step 5: Wire constitution principle

Add to `.specify/memory/constitution.md`:

> **UI compliance (MUST).** All UI, template, and CSS work MUST comply with `docs/ux-rules.md`. S4/S3 findings block; resolve them, never dilute the rule.

Then run `/speckit.constitution` to propagate.

## Verification

```bash
# Test the linter
make ux-lint FILES="docs/ux-rules.md"    # should pass (no template patterns)
echo '{{ x | safe }}' > /tmp/test.html
make ux-lint FILES="/tmp/test.html"      # should fail with [S4] template
rm /tmp/test.html

# Verify skills load
# Open the `skill` tool and confirm ux-review and ux-generate appear at project priority

# Verify constitution check
# Run `/speckit.analyze` on a spec with UI changes — should reference UI compliance
```