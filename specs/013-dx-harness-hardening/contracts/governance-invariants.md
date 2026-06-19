# Contract: Governance Invariants

This contract defines the machine-and-review-checkable invariants the governance/consistency workstream must satisfy. These are verified by `make vault-audit`, the new helper scripts, and structured review.

## INV-1 — No contradictory rules across documents (FR-007)

- **Statement**: Any rule appearing in more than one of {`.specify/memory/constitution.md`, `AGENTS.md`, `CONTRIBUTING.md`} states the same requirement.
- **Verification**: Review checklist cross-references each shared rule. Specifically, the `TYPE_CHECKING` rule must read identically (in intent) across the constitution and `AGENTS.md`.
- **Pass**: 0 contradictions.

## INV-2 — No knowingly-violated rule (FR-008)

- **Statement**: For every declared rule, either the code complies or the rule was amended via an ADR.
- **Verification**: Each review-flagged rule is checked: `TYPE_CHECKING` (code complies after `inference.py` refactor + amendment); coverage (enforced = declared); `mypy` `ignore_errors` overrides (removed, or narrowed to specific codes + ADR-justified).
- **Pass**: 0 standing knowing violations.

## INV-3 — Coverage honesty (FR-009, FR-010)

- **Statement**: `pyproject.toml [tool.coverage.report] fail_under` equals the value declared in governance, is satisfiable on `main` today, and never decreases without recorded approval.
- **Verification**: CI `test` gate passes on `main`; constitution Article IV text matches the `fail_under` policy; ratchet (decrease requires ADR/approval) documented.
- **Pass**: declared == enforced; current `main` passes.

## INV-4 — ADR identifier uniqueness (FR-011)

- **Statement**: Every ADR file has a unique `ADR-0NN` identifier; no two share a number; no inbound wikilink is broken.
- **Verification**: `adr-uniqueness` check (in `vault_audit.py` or `scripts/ci/check_adr_unique.py`) reports 0 duplicate numbers; `vault-audit` link resolution reports 0 broken links after renumbering 008/010/016 and adding redirect stubs.
- **Pass**: 0 duplicate numbers, 0 broken links.

## INV-5 — Amendment provenance (FR-012)

- **Statement**: Every governance amendment in this feature has a dated, versioned ADR stating rationale, and the constitution version is bumped.
- **Verification**: ADRs exist for coverage-ratcheting, type-checking-conditional-allow, CI-merge-gate-enforcement, ADR-renumbering-and-uniqueness (and mypy-narrowing if taken); constitution `**Version**` line incremented with updated "Last Amended" date.
- **Pass**: 1 ADR per amendment; version bumped.

## INV-6 — `TYPE_CHECKING` policy & discipline (FR-021, FR-022)

- **Statement**: Governance states one conditional-allow policy; every guarded import in the codebase satisfies the 4-point discipline.
- **Verification**:
  - `anvil/db/models/corpus.py`, `corpus_file.py`: retain guard, have `from __future__ import annotations`, have the one-line cycle comment, symbol used only in annotations.
  - `anvil/services/inference/inference.py`: no guarded import remains; `Value` imported at top level; redundant local import removed.
  - `guarded-imports` check: 0 guarded symbols used in runtime code.
- **Pass**: only the 2 ORM guards exist; all satisfy discipline; checker green.

## INV-7 — Agent-guide leanness (FR-016, SC-009)

- **Statement**: `AGENTS.md` contains durable rules only; per-change history lives in `CHANGELOG.md`.
- **Verification**: `AGENTS.md` has no "Recent Changes"/per-feature changelog entries; that content is present in `CHANGELOG.md`.
- **Pass**: 0 per-change history entries in `AGENTS.md`.

## INV-8 — Docs match reality (FR-013, FR-014, FR-015, FR-017)

- **Statement**: `ARCHITECTURE.md` exists and accurately describes the layering/access patterns *after* the P4 refactors; `CONTRIBUTING.md` orients newcomers; a tooling-free ADR index exists.
- **Verification**: Architecture doc's described service-access pattern matches the consolidated god class (FR-018); ADR index (`docs/vault/Decisions/README.md`) lists all ADRs; new-contributor walkthrough (quickstart) succeeds.
- **Pass**: described structure == actual structure; index complete.
