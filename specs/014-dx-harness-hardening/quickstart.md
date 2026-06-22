# Quickstart: Developer & Agent Experience Hardening

This quickstart describes the *experience* the feature delivers and how to verify it. It doubles as the acceptance walkthrough.

## For a contributor (human or agent) opening a change

1. Make your change on a feature branch.
2. Run the gates locally — the exact commands CI runs:
   ```bash
   make lint        # ruff → black --check → isort --check → pylint
   make typecheck   # mypy --strict
   make test        # pytest + coverage (must meet fail_under)
   make vault-audit # frontmatter, wikilinks, vocabulary, ADR uniqueness
   ```
3. Open a pull request into `main`.
4. CI runs the same suite. If anything fails, the PR check is red and the log names the specific gate and offending file/rule. Fix and push; CI re-runs.
5. When all required checks are green, the PR is mergeable. **A red or missing check blocks merge** (fail-closed).

**Parity guarantee**: step 2 (local) and step 4 (CI) run the identical `make` targets — no "passes locally, fails in CI" surprises (FR-005).

## For an automated version bump (release flow)

- A bot PR that touches only the version line + `CHANGELOG.md` passes the `bump-scope-guard` and skips the heavy gates, so releases stay fast.
- If a PR also touches any source/test file, the full gate suite runs — no bypass for code changes (FR-006a).

## For a newcomer (first 15 minutes)

1. Open `ARCHITECTURE.md` (repo root): understand the layering model (Repository → Service → `AnvilWorkbench` → Routes/CLI), the data flow, and "how to add a service/route".
2. Open `CONTRIBUTING.md`: code map, the mandatory rules digest, and the local gate commands above.
3. Browse `docs/vault/Decisions/README.md`: a plain-markdown index of every architectural decision and its rationale — no Obsidian required.
4. From a fresh clone:
   ```bash
   make setup       # venv + deps
   make test        # should pass and report coverage at/above the baseline
   make lint && make typecheck && make vault-audit
   ```
   All green = your environment matches CI (SC-008).

## Adding a new architecture decision

1. Copy `docs/vault/Decisions/ADR-template.md`.
2. Assign the **next free** `ADR-0NN` number (the `adr-uniqueness` gate rejects duplicates).
3. Fill title, status (`draft`), date, rationale.
4. Link it from `docs/vault/Decisions/README.md` (or let `make vault-audit` regenerate/validate the index).
5. `make vault-audit` must pass before commit.

## Using a `TYPE_CHECKING`-guarded import (rare)

Permitted **only** to break a genuine unavoidable runtime cycle (e.g., the `Corpus`↔`CorpusFile` ORM relationship). Each use must:
1. Have `from __future__ import annotations` in the module.
2. Use the symbol **only** in annotations (the `guarded-imports` gate enforces this).
3. Carry a one-line comment naming the cycle, e.g. `# TYPE_CHECKING-only: breaks Corpus<->CorpusFile ORM cycle`.

Otherwise use a normal top-level import. (This is exactly why `services/inference/inference.py` was refactored away from a guard.)

## Verification matrix (maps to Success Criteria)

| Walkthrough step | Verifies |
|---|---|
| Red check blocks merge | SC-001, FR-003 |
| Local == CI commands | FR-005 |
| `fail_under` passes on `main` | SC-004, FR-009 |
| Bump PR fast-path | FR-006a |
| Newcomer 15-min clone-to-green | SC-008 |
| ADR index browsable without tooling | SC-005, FR-015 |
| `guarded-imports` green; only 2 ORM guards | INV-6, FR-022 |
| Each refactor: suite identical before/after | SC-011, FR-020 |
