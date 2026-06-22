# Tasks: Automated Semantic Versioning & Release

**Input**: Design documents from `specs/010-automated-semver-release/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **`.github/workflows/`**: GitHub Actions workflow files
- **Project root**: `pyproject.toml`, `CHANGELOG.md`
- All paths relative to repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install commitizen tooling, configure version management, create changelog

- [X] T001 Add `commitizen` to `[project.optional-dependencies].dev` in `pyproject.toml`
- [X] T002 Add `[tool.commitizen]` configuration section to `pyproject.toml` with `cz_conventional_commits`, semver scheme, pep621 version provider, and changelog auto-update settings
- [X] T003 Create `CHANGELOG.md` at repository root with Conventional Commits header template
- [X] T004 Validate commitizen config by running `cz bump --dry-run --increment patch` (expects exit 0)

**Checkpoint**: commitizen is installed and configured. Running `cz version` shows the installed version.

---

## Phase 2: User Story 1 — Developer commits with conventional commit format (Priority: P1) 🎯 MVP

**Goal**: Developers can create commits using conventional commit format (via `cz commit` or manually). Non-conventional commits are rejected locally.

**Independent Test**: A developer creates a commit with `cz commit` and it succeeds. They then attempt `git commit -m "fixed stuff"` and the commit-msg hook rejects it with a helpful error message.

### Implementation

- [X] T005 [P] [US1] Configure commit message enforcement via pre-commit or git hooks in `.githooks/commit-msg` that runs `cz check --commit-msg-file $1`
- [X] T006 [US1] Verify local enforcement — create a test commit with valid conventional format (should be accepted) and one with invalid format (should be rejected with helpful message)
- [X] T007 [US1] Verify `cz commit` interactive prompt — run `echo -e "feat\n\nadd test endpoint\n\nn\n" | cz commit` to simulate interactive input and confirm exit 0

**Checkpoint**: Local enforcement is working. Invalid commit messages are caught before push. Valid conventional commits are accepted.

---

## Phase 3: User Story 2 — Release triggered on merge to main with changelog and tag (Priority: P1) 🎯 MVP

**Goal**: When a PR with a conventional commit title is merged to main, the release workflow automatically determines the bump type, updates version and changelog, creates a tag, and publishes a GitHub Release.

**Independent Test**: Create a test PR with title `feat: add test widget`, merge to main via squash. Verify that within 5 minutes: (1) version in `pyproject.toml` is bumped (e.g., `0.1.0` → `0.2.0`), (2) `CHANGELOG.md` has a `### Feat` entry, (3) git tag `v0.2.0` exists, (4) GitHub Release `v0.2.0` is published.

### Implementation

- [X] T008 [P] [US2] Create `.github/workflows/release.yml` with push-to-main trigger, `workflow_dispatch` escape hatch, and `concurrency` group (no cancel-in-progress)
- [X] T009 [P] [US2] Implement `check-version` job in `.github/workflows/release.yml` — reads version from `pyproject.toml`, compares with parent commit, outputs `version_changed` and `version`
- [X] T010 [US2] Implement conventional commit type detection — parse merge commit message for `BREAKING CHANGE`, `feat:`, `fix:` prefixes to determine MAJOR/MINOR/PATCH bump
- [X] T011 [US2] Integrate commitizen bump command: `cz bump --yes --changelog --increment {MAJOR|MINOR|PATCH}` updates `pyproject.toml` version and appends `CHANGELOG.md` entry
- [X] T012 [US2] Implement bump PR creation — create a branch, commit version/changelog changes with `[skip ci]`, open PR via `gh pr create` using `BUMP_PAT`, auto-merge via `gh pr merge --auto --squash`
- [X] T013 [US2] Implement tag creation and GitHub Release — `git tag v{VERSION}`, `git push origin v{VERSION}`, `gh release create` with changelog extraction from `CHANGELOG.md`
- [X] T014 [US2] Add BUMP_PAT preflight check — verify secret is available before attempting PR creation, fail early with clear diagnostic if missing
- [X] T015 [US2] Add idempotent re-run handling — detect existing tag/changelog entry and skip gracefully if already created
- [X] T016 [US2] Add infinite loop prevention — verify `[skip ci]` is in bump commit message, add loop detection (abort if two releases triggered within 60s with no intervening human commits)

**Checkpoint**: A squash-merged PR with `fix:` or `feat:` title produces a complete release cycle (version bumped, changelog updated, tag created, release published).

---

## Phase 4: User Story 3 — Maintainer publishes release notes from PR descriptions (Priority: P2)

**Goal**: Release notes include PR description body content alongside the auto-generated changelog entry, capturing migration notes, breaking change details, and usage guidance.

**Independent Test**: Merge a PR with a PR description containing structured sections. Verify the resulting GitHub Release body includes those sections. Merging a PR with an empty description produces release notes with only the changelog section.

- [X] T017 [P] [US3] Implement PR description fetch in `.github/workflows/release.yml` — use `gh pr list --state merged --head <branch> --json body --jq '.[0].body'` to retrieve PR description
- [X] T018 [US3] Integrate PR description into release notes — append PR body content to the release notes file after the changelog entry (handle empty/null gracefully)
- [X] T019 [US3] Add graceful degradation — if PR description fetch fails (rate limit, API error), log warning and continue with changelog-only release notes (AR-005)

**Checkpoint**: GitHub Release body includes both changelog and PR description context. Empty descriptions don't cause errors.

---

## Phase 5: User Story 4 — Safety-net auto-bump for un-versioned changes (Priority: P3)

**Goal**: If source code lands on main without a version bump, an auto-bump PR is automatically created to apply a patch version increment.

**Independent Test**: Push a commit to main modifying `anvil/` source files without changing the version. Verify an auto-bump PR is created with patch increment. Push only docs/CI changes — verify no PR is created.

- [X] T020 [US4] Create `.github/workflows/auto-bump.yml` with push-to-main trigger on `anvil/**` paths (excluding `CHANGELOG.md` and `.github/`), plus `workflow_dispatch` escape hatch and `concurrency` group
- [X] T021 [US4] Implement version-change detection in auto-bump — read `pyproject.toml` version, compare with parent commit
- [X] T022 [US4] Implement auto-bump PR creation — if version not changed, increment patch, update `pyproject.toml` and `CHANGELOG.md`, create branch, open PR via `gh pr create` (BUMP_PAT), auto-merge via `gh pr merge --auto --squash`
- [X] T023 [US4] Add path exclusion — verify auto-bump does NOT trigger for commits that only modify `CHANGELOG.md`, `.github/`, or other non-source paths
- [X] T024 [US4] Add loop prevention — include `[skip ci]` in auto-bump commit messages, add cycle-detection guard

**Checkpoint**: Source-only changes pushed to main without version bump trigger an auto-bump PR. Non-source changes don't trigger.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verification, documentation, and hardening

- [X] T025 Run linting across all changed files — `make lint` passes
- [X] T026 Verify existing test suite still passes — `make test` exits 0
- [X] T027 [P] Add documentation references in `AGENTS.md` for the new CI/CD tooling (commitizen, release workflow, auto-bump)
- [X] T028 [P] Run the agentic checklist from spec.md and confirm all items pass
- [X] T029 [P] Verify quickstart.md — run each command in quickstart.md from a fresh repo clone and confirm exit 0
- [X] T030 [P] Write BUMP_PAT secrets documentation — create or update a doc file at `docs/secrets.md` with step-by-step instructions for creating the fine-grained PAT (Contents: write, Pull requests: write, Workflows: write) in GitHub Settings → Secrets → Actions
- [X] T031 [P] Verify SC-003 — run `pip install -e .[dev] && echo -e "feat\n\nadd test endpoint\n\nn\n" | cz commit` to simulate a new contributor's first conventional commit from a fresh install

---

## Dependencies & Execution Order

### Phase Dependencies

| Phase | Depends On | Description |
|-------|-----------|-------------|
| **Phase 1** (Setup) | — | No dependencies, start here |
| **Phase 2** (US1) | Phase 1 | Needs commitizen installed for local enforcement |
| **Phase 3** (US2) | Phase 1 | Needs commitizen configured for CI usage (does NOT need US1) |
| **Phase 4** (US3) | Phase 3 | Enhances the release workflow with PR description fetching |
| **Phase 5** (US4) | Phase 3 | Reuses version detection and PR creation patterns from US2 |
| **Phase 6** (Polish) | All | Verifies everything works together |

### Key Independence (Important)

- **US1 (Phase 2) and US2 (Phase 3) are independent** — both depend on Phase 1 but NOT on each other. Local enforcement (commit hooks) and CI release workflow can be developed in parallel.
- **US3 (Phase 4) depends on US2** — it enhances the release workflow with PR description content in release notes.
- **US4 (Phase 5) depends on US2** — it reuses the version detection and PR patterns established in the release workflow.

### Within Each Phase

- [P] marked tasks can run in parallel
- Tasks without [P] have implicit ordering dependencies
- Each checkpoint can be validated before proceeding

---

## Parallel Opportunities

```bash
# Phase 1: All can run in parallel
Task: T001 - Add commitizen to dev deps (pyproject.toml)
Task: T002 - Add [tool.commitizen] config (pyproject.toml)
Task: T003 - Create CHANGELOG.md header

# Phase 2 + Phase 3: US1 and US2 can run in parallel
# Developer A: Phase 2 (US1 - Local enforcement)
# Developer B: Phase 3 (US2 - Release workflow)
Task: T005 - configure commit hooks
Task: T008 - create release.yml workflow
Task: T009 - implement check-version job

# Phase 4 (US3) starts after Phase 3 (US2) complete
# Phase 5 (US4) starts after Phase 3 (US2) complete

# Phase 6: Polish tasks in parallel
Task: T025 - make lint
Task: T026 - make test
Task: T027 - update AGENTS.md
T028 - run agentic checklist
T029 - verify quickstart
T030 - document secrets
T031 - verify first commit from fresh install
```

---

## Implementation Strategy

### MVP First (Phase 2 + Phase 3 — Both P1)

1. **Complete Phase 1**: Setup — commitizen config + CHANGELOG.md
2. **Complete Phase 2**: US1 — Local commit enforcement (independent of US2)
3. **Complete Phase 3**: US2 — Release workflow (independent of US1)
4. **STOP and VALIDATE**: Both P1 stories work independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Phase 1 (Setup) → Foundation ready
2. Phase 2 + Phase 3 in parallel → **MVP!** (Both P1 stories deliver core value)
3. Phase 4 (US3) → Release notes enriched with PR descriptions
4. Phase 5 (US4) → Safety-net auto-bump
5. Phase 6 (Polish) → Verification and documentation

### Parallel Team Strategy

With two developers:
1. Both complete Phase 1 together (5 minutes of config)
2. Developer A: Phase 2 (US1 — Local enforcement, ~4 tasks)
3. Developer B: Phase 3 (US2 — Release workflow, ~9 tasks)
4. Both integrate their PRs
5. Developer A or B: Phase 4 (US3 — PR descriptions)
6. Anyone: Phase 5 (US4 — Auto-bump)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story phase should be independently completable and testable
- Commit after each story phase (or logical group within phase)
- Stop at any checkpoint to validate story independently
- This feature introduces NO new Python modules — all work is YAML workflow files + pyproject.toml edits + CHANGELOG.md creation