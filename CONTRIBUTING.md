# Contributing to anvil

## Development Setup

```bash
make setup   # Creates venv, installs deps, runs migrations
```

## Commands

| Command | Purpose |
|---------|---------|
| `make test` | Run tests |
| `make lint` | Run ruff → black --check → isort --check → pylint |
| `make format` | Auto-format with black + isort |
| `make typecheck` | Run mypy |

## Commit Conventions

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat: add dataset upload endpoint`
- `fix: correct SSE reconnection handling`
- `docs: update README with new routes`
- `test: add experiment comparison tests`

## Pull Request Process

1. All tests must pass
2. Lint must pass
3. 100% coverage must be maintained
4. ADR required for significant architecture decisions