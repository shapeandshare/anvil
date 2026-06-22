# Contract: Makefile Targets

## Targets

### `make ux-lint`

Deterministic mechanical S4 gate. Zero dependencies, no network, no API key.

**Usage**:
```bash
make ux-lint                              # lint changed files vs origin/main
make ux-lint FILES="templates/*.html"     # lint specific files/globs
```

**Exit behavior**: Non-zero if any unsuppressed S4 finding exists.

**Default `FILES`**: UI/template files changed vs `origin/main` (HTML, Jinja, CSS, JS/TS, Vue, Svelte, Python).

**Suppression**: `ux-lint:allow` on the finding's line, `ux-lint:allow-next` on the preceding line.

### `make ux-review`

Optional AI-powered full-ruleset review. Requires `UX_API_KEY`.

**Usage**:
```bash
UX_API_KEY="sk-..." make ux-review                    # review changed files
UX_API_KEY="sk-..." make ux-review FILES="*.html"     # review specific files
```

**Exit behavior**: Non-zero if findings at or above S3 severity.

**Configuration**: See `UX_*` env vars below.

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `UX_API_KEY` | For `ux-review` | — | Bearer token for OpenAI-compatible endpoint |
| `UX_MODEL_BASE_URL` | No | `https://openrouter.ai/api/v1` | API base URL |
| `UX_MODEL` | No | `anthropic/claude-sonnet-4.6` | Model identifier |
| `UX_RULES` | No | `docs/ux-rules.md` | Ruleset path (local file or URL) |
| `UX_GATE` | No | `3` | Minimum severity to fail (S3=3, S4=4) |

## File Extension Matching

The `FILES` default filters changed files against these extensions:

```
html|htm|jinja|jinja2|j2|css|scss|sass|less|js|jsx|ts|tsx|vue|svelte|py
```