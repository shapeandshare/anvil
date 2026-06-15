# Contract: Conventional Commit Message Format

**Purpose**: Define the commit message format that the release workflow uses to determine version bump types and generate changelog entries.

**Applies to**: All commits on the `main` branch (via squash-merge PR titles)

## Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Type (required)

Determines the version bump level:

| Type | Bump | Description | Example |
|------|------|-------------|---------|
| `feat` | MINOR | A new feature for the user | `feat: add dataset comparison view` |
| `fix` | PATCH | A bug fix | `fix: correct tokenizer overflow` |
| `perf` | PATCH | Performance improvement | `perf: reduce memory usage in inference` |
| `refactor` | NONE | Code refactoring | `refactor: extract validation logic` |
| `chore` | NONE | Maintenance tasks | `chore: update dependencies` |
| `docs` | NONE | Documentation changes | `docs: add API usage guide` |
| `ci` | NONE | CI configuration changes | `ci: add release workflow` |
| `test` | NONE | Test additions/updates | `test: add training pipeline tests` |
| `style` | NONE | Code style/formatting | `style: format with black` |
| `build` | NONE | Build system changes | `build: upgrade to Python 3.12` |

### Scope (optional)

A noun indicating which part of the codebase is affected:
- `core` — training engine (`anvil/core/`)
- `api` — web server routes (`anvil/api/`)
- `db` — database layer (`anvil/db/`)
- `services` — business logic (`anvil/services/`)
- `ui` — frontend templates/static
- `cli` — CLI commands
- `deps` — dependencies only
- `ci` — CI/CD configuration

### Description (required)

Short, imperative tense description. No period at end.

### Breaking Changes

Indicated by one of:
- Appending `!` after type/scope: `feat!: ...`
- Including `BREAKING CHANGE:` in the footer
- Triggers a MAJOR version bump

### Body (optional)

Provides additional context. Used in changelog.

### Example

```
feat(core): add RoPE positional encoding

Implement rotary position embeddings for the transformer,
replacing the learned wpe table.

BREAKING CHANGE: Existing checkpoints with learned wpe
will not be compatible with this change.
```

## PR Title Mapping

When a PR is squash-merged, the PR title becomes the squash-merge commit message. Therefore:
- PR titles MUST follow the conventional commit format
- PR descriptions flow into the commit body
- The release workflow reads the merge commit message to determine bump type

## Validation

```bash
# Check specific commit
cz check --rev-range HEAD~1..HEAD

# Check staged commit message (via hook)
cz check --commit-msg-file <path>

# Valid: exits 0
cz check --rev-range HEAD~1..HEAD
echo $?  # 0

# Invalid: exits non-zero with error message
echo "fixed stuff" | cz check --commit-msg-file /dev/stdin
echo $?  # non-zero
```