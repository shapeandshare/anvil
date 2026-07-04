# Contributing to anvil

First off, thank you for considering contributing to anvil.

All community interactions — issues, discussions, pull requests, and any other
communication — are governed by our [Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you agree to uphold its standards.

> **Questions?** Check [SUPPORT.md](SUPPORT.md) for where to ask.
> **Found a security issue?** See [SECURITY.md](SECURITY.md) for responsible
> disclosure.

## Community Guidelines

### Be constructive

The project follows a **pit-of-success** design philosophy — defaults lead to
correct behavior. Please bring the same mindset to contributions:

- **Bug reports**: include a minimal reproduction, expected vs. actual behavior,
  and environment details. Track down the root cause if you can — `git bisect`
  is your friend.
- **Feature discussions**: start with the problem you're solving, not the
  solution you've settled on. The simplest, most boring solution that works is
  preferred (see [Article XI — Simplicity First](.specify/memory/constitution.md)).
- **Pull requests**: explain *what* the change does and *why* it's needed. Keep
  diffs focused — one change per PR. A 1-line fix with a clear commit message
  is better than a 20-line refactor that also fixes the bug.

### Communication norms

- **Search before posting**: check existing issues, discussions, and PRs before
  opening a new one.
- **Assume good faith**: everyone is here to learn and improve the project.
  Disagreement on technical approach is normal — address the idea, not the
  person.
- **Reviewer patience**: maintainers review in their free time. If a PR hasn't
  been reviewed in a week, a polite ping on the thread is fine. Daily bumps are
  not.

### Agentic development (AI-native workflow)

anvil is developed and maintained **primarily through AI agents** — this is by
design, not by accident. The project's [AGENTS.md](AGENTS.md) defines how
agents should operate in this codebase, and the
[Constitution](.specify/memory/constitution.md) encodes the architectural
rules all agents must follow.

#### For human contributors using AI tools

If you're a human using AI coding tools (Claude, Cursor, Copilot, etc.) to
contribute to anvil, you are working in the same way the project maintainer
does. Welcome. Please ensure:

1. **You understand the change** — you can explain every line. AI agents produce
   plausible-looking code that may be subtly wrong.
2. **You run the gates locally** — `make test`, `make lint`, `make typecheck`,
   `make vault-audit` before opening a PR.
3. **You follow the TDD mandate** — tests first, then implementation. The
   project's [Constitution Article IV](.specify/memory/constitution.md#article-iv--tdd-mandatory)
   applies to all contributions, regardless of origin.
4. **You self-identify** — if your PR or issue was generated with AI assistance,
   briefly note which tool and model you used. This helps maintainers understand
   the context of the contribution.

#### For autonomous agents

If you are an AI agent filing an issue or PR autonomously, you MUST:

1. **Follow AGENTS.md** — the behavioral guidelines in AGENTS.md are binding on
   all agents operating in this repository.
2. **Self-identify as an agent** — in the issue/PR body, declare your identity
   (which agent system/model you are) and that you are operating autonomously.
3. **Respect rate limits** — do not spam. File one well-researched issue or PR
   at a time.
4. **Pass all CI gates** — the same gates apply. No special treatment.
5. **Include a reproduction or test** — every claim about a bug or feature must
   be backed by a test case or reproduction script.

#### What gets rejected

Contributions are likely to be closed without review if they:

- Appear to be bulk-generated without understanding (e.g., 50 nearly identical
  "fix typo" PRs from different accounts)
- Show no evidence of testing (`make test` would fail)
- Violate the TDD mandate (implementation without tests)

## Development Setup

```bash
make setup   # Creates venv, installs deps, runs migrations
```

## Commands

| Command | Purpose |
|---------|---------|
| `make test` | Run tests (with coverage; must meet `fail_under` in `pyproject.toml`) |
| `make lint` | Run ruff → black --check → isort --check → pylint |
| `make format` | Auto-format with black + isort |
| `make typecheck` | Run mypy (strict) |
| `make vault-audit` | Run vault audit (frontmatter, wikilinks, vocabulary, ADR uniqueness) |
| `make adr-check` | Validate ADR naming conventions and identifier uniqueness |
| `make guarded-imports-check` | Validate TYPE_CHECKING imports are annotation-only |

## Commit Conventions

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat: add dataset upload endpoint`
- `fix: correct SSE reconnection handling`
- `docs: update README with new routes`
- `test: add experiment comparison tests`

## Pull Request Process

1. All gates (`make lint`, `make typecheck`, `make test`, `make vault-audit`) must pass
2. Coverage must meet the ratcheting baseline (`fail_under` in `pyproject.toml`)
3. ADRs must have unique, sequential identifiers (enforced by `make adr-check`)
4. TYPE_CHECKING imports must be annotation-only (enforced by `make guarded-imports-check`)
5. ADR required for significant architecture decisions

### Branch protection

The `main` branch requires the CI workflow to pass before merge. The workflow runs five gates:
- **Bump-scope guard**: classifies PRs as version-only or full-source. Version-only bumps (pyproject version line + CHANGELOG) skip the heavy gates to keep automated releases fast.
- **Lint**, **Type Check**, **Test**, **Vault Audit**: required for every source-code change.

If a gate fails, the CI check shows red, logs the specific failure, and blocks merge. If the CI infrastructure fails (timeout, outage), merge is also blocked (fail-closed). This protects against regression while keeping the automated release pipeline flowing.

## Related Documents

- [Code of Conduct](CODE_OF_CONDUCT.md) — community behavior standards
- [Security Policy](SECURITY.md) — vulnerability disclosure
- [Support](SUPPORT.md) — where to ask questions
- [Constitution](.specify/memory/constitution.md) — project architecture rules and principles
- [AGENTS.md](AGENTS.md) — agent behavioral guidelines

---

&copy; 2026 Josh Burt. Released under the MIT License.