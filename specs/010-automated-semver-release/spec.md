# Feature Specification: Automated Semantic Versioning & Release

**Feature Branch**: `010-automated-semver-release`  
**Created**: 2026-06-14  
**Status**: Draft  
**Input**: User description: "we should be using commitizen for semantic versioning. on merge to main we automatically trigger the version bump, this should include the changelog entry, we must use pr titles, descriptions to help with this, we want to release tag our stuff as well -- we should be able to find these patterns in the repos we have locally in ~/Workbench/Repositories"

## Clarifications

### Session 2026-06-14

- Q: How should the version bump commit get back to main without infinite loops or branch protection failures? → A: Auto-merge PR pattern — workflow creates a PR with the bump commit, auto-merges via `gh pr merge --auto --squash`, uses `BUMP_PAT` for PR creation, and includes `[skip ci]` in the bump commit message to prevent re-triggering the release workflow.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer commits with conventional commit format (Priority: P1)

A developer makes changes and commits them using the conventional commit format (e.g., `feat: add dataset comparison view`, `fix: correct tokenizer overflow`). They follow the commitizen convention either via a CLI prompt (`cz commit`) or by writing conventional commit messages manually. The project enforces conventional commit formatting on all commits landing on the main branch.

**Why this priority**: Conventional commits are the foundation of automated semantic versioning. Without structured commit messages, the system cannot determine what type of version bump to apply or generate meaningful changelog entries.

**Independent Test**: A developer installs the project dependencies, runs `cz commit` (or writes a conventional commit message manually), and the commit is accepted by the local git hook. Running `cz check --rev-range HEAD~1..HEAD` confirms the commit message adheres to the conventional commits standard.

**Agent Verification Signal**: Implementer confirms that `cz check --rev-range HEAD~1..HEAD` exits 0 after creating a valid conventional commit, and exits non-zero with a helpful error message after creating an invalid one.

**Acceptance Scenarios**:

1. **Given** a developer has anvil checked out with commitizen configured, **When** they run `cz commit` and select a commit type (feat, fix, chore, etc.), **Then** the resulting commit message follows the conventional commit format (e.g., `feat(scopes): description`).

2. **Given** a developer writes a commit message manually, **When** they commit with a non-conventional format (e.g., `fixed stuff`), **Then** a commit-msg hook rejects the commit and displays the required format.

3. **Given** a developer writes a commit with a breaking change indicator (`feat: ... BREAKING CHANGE: ...`), **When** the commit is created, **Then** the commitizen tooling recognizes the breaking change for a future major version bump.

---

### User Story 2 - Release triggered on merge to main with changelog and tag (Priority: P1)

A pull request with a conventional-commit-style title is merged into main via squash merge. The merge triggers an automated workflow that:
1. Reads the squash-merge commit message (containing the PR title/description)
2. Determines the appropriate semantic version bump (major, minor, or patch) from the conventional commit type
3. Updates `pyproject.toml` with the new version number
4. Appends a changelog entry to `CHANGELOG.md` describing the change
5. Creates a new PR with the version/changelog bump (commit message includes `[skip ci]`)
6. Auto-merges the bump PR via `gh pr merge --auto --squash`
7. Creates a git tag (`vX.Y.Z`) and GitHub Release with release notes

**Why this priority**: This is the core value delivery — automated versioning, changelog, and releases that remove manual overhead and ensure every merge to main produces a consistent, traceable release.

**Independent Test**: A test PR with title `feat: add widget` is merged to main. Within minutes, a new GitHub Release appears with tag `v0.2.0`, the version in `pyproject.toml` reads `0.2.0`, and CHANGELOG.md contains a `### Feat` section describing the widget addition.

**Agent Verification Signal**: Implementer runs the workflow locally (or on a test branch) and confirms that `git tag --list 'v*'` includes the new tag, `pyproject.toml` version field is updated, `CHANGELOG.md` contains a new entry for the version, and the GitHub Release API returns the expected release object.

**Acceptance Scenarios**:

1. **Given** a PR with title `fix: correct tokenizer overflow` is squash-merged to main, **When** the automated release workflow runs, **Then** a patch version bump occurs (e.g., `0.1.0` → `0.1.1`), CHANGELOG.md gains a `### Fix` entry, and a GitHub Release is created with tag `v0.1.1`.

2. **Given** a PR with title `feat: dataset comparison view` is squash-merged to main, **When** the workflow runs, **Then** a minor version bump occurs (e.g., `0.1.1` → `0.2.0`), and CHANGELOG.md gains a `### Feat` entry.

3. **Given** a PR title containing `BREAKING CHANGE` or `!` indicator, **When** the workflow runs, **Then** a major version bump occurs (e.g., `0.2.0` → `1.0.0`).

4. **Given** a PR with type `chore:`, `docs:`, or `ci:` (non-user-facing changes), **When** the workflow runs, **Then** no version bump occurs, but a changelog entry is still created under the appropriate section.

---

### User Story 3 - Maintainer publishes release notes from PR descriptions (Priority: P2)

When a release is created, the release body includes both the auto-generated changelog section and any additional context from the PR description. This ensures release notes are informative and include migration notes, breaking change details, and usage guidance.

**Why this priority**: PR descriptions often contain richer context than commit messages. Including this context in release notes makes releases more useful for downstream users (both human readers and automated consumers).

**Independent Test**: A PR is merged with a description containing "## Migration Notes: ..." and "## Breaking Changes: ...". The resulting GitHub Release body includes these sections alongside the changelog entries.

**Agent Verification Signal**: Implementer inspects the generated release notes via GitHub API and confirms the PR description body sections appear in the release body. They also confirm an empty PR description produces release notes with only the changelog section.

**Acceptance Scenarios**:

1. **Given** a PR description contains structured sections (e.g., "## Migration Notes"), **When** the merge workflow creates the release, **Then** the PR description body is included in the release notes.

2. **Given** a PR description is empty, **When** the release is created, **Then** the release notes contain only the auto-generated changelog section without errors.

---

### User Story 4 - Safety-net auto-bump for un-versioned changes (Priority: P3)

Code changes that land on main without a conventional-commit PR title (e.g., direct pushes, emergency hotfixes, or workflow-suppression edge cases) are caught by a safety-net workflow that opens a patch-bump PR automatically.

**Why this priority**: This is a defensive measure that prevents version drift. The primary enforcement is the release workflow itself, but edge cases (direct pushes, GitHub workflow suppression) need a backstop.

**Independent Test**: A direct push to main that modifies source files but not the version number triggers the auto-bump workflow. A new PR is opened that bumps the patch version and adds a "chore: auto bump" changelog entry.

**Agent Verification Signal**: Implementer pushes a test commit to main (or a test branch mimicking the same trigger path) that modifies source files without a version change, then confirms a PR is auto-created with the expected bump. A follow-up test with only docs/CI changes confirms no PR is created.

**Acceptance Scenarios**:

1. **Given** a commit lands on main that modifies `anvil/` source files without a version change, **When** the auto-bump workflow runs, **Then** a PR is automatically created that bumps the patch version and adds an appropriate changelog entry.

2. **Given** a commit that only modifies documentation or CI config, **When** the auto-bump check runs, **Then** no bump PR is created.

---

### Edge Cases

- **Non-conventional commit on merge**: If a merge commit message does not follow conventional commit format, the workflow gracefully skips the version bump and logs a warning. The release is not created. A manual workflow_dispatch trigger provides an escape hatch.
- **Existing tag collision**: If a tag `vX.Y.Z` already exists (should not happen with auto-incrementing), the workflow must NOT overwrite the existing tag. Instead, it must either: (a) detect the collision and fail with a clear error message and manual-resolution instructions, or (b) create the tag with a disambiguating suffix. Option (a) is preferred for safety.
- **Infinite loop prevention**: The version bump commit created by the release workflow MUST include `[skip ci]` in the commit message to prevent re-triggering the release workflow. Additionally, the auto-merge PR pattern (not direct push) ensures the bump commit goes through the normal PR flow without a second run. If a loop is detected (two releases triggered in rapid succession with no intervening human commits), the workflow should abort and log a warning.
- **Workflow suppression**: GitHub may suppress push-based workflows when a merge commit touches `.github/workflows/` files. The release workflow supports `workflow_dispatch` as a manual escape hatch.
- **Concurrent merges**: If two PRs merge to main in quick succession, the release workflow uses `concurrency` settings to queue releases rather than running them in parallel, preventing tag conflicts and race conditions.
- **Changelog format migration**: If a CHANGELOG.md already exists with a different format, the workflow prepends to it rather than overwriting. The commitizen tool is configured with `changelog_incremental = true` to append new entries.
- **Idempotent re-run**: If a workflow run fails mid-way (e.g., tag created but release publish failed), re-running the workflow must be safe. The implementer MUST handle partial-state recovery: detect existing tag, detect existing changelog entry, skip or reconcile.
- **GitHub token limits**: The `GITHUB_TOKEN` has known restrictions (cannot trigger downstream workflows from pushed commits, PRs opened by GITHUB_TOKEN bypass CI checks). The workflow must use a fine-grained PAT (`BUMP_PAT`) for any step that creates PRs. If `BUMP_PAT` is missing or expired, the workflow must fail early with a clear diagnostic message, not silently degrade.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST adopt Commitizen with the `cz_conventional_commits` backend for commit message enforcement and version management.
- **FR-002**: Commitizen MUST be configured with semantic versioning (`version_scheme = "semver"`) and tag format `v$version`.
- **FR-003**: The version source MUST be `pyproject.toml` (PEP 621), consistent with the existing project setup.
- **FR-004**: Commitizen MUST be configured to update CHANGELOG.md automatically on bump (`update_changelog_on_bump = true`, `changelog_incremental = true`).
- **FR-005**: A GitHub Actions workflow MUST trigger on push/merge to the `main` branch and perform automated version detection and release.
- **FR-006**: The workflow MUST determine the version bump level from the merge commit message (squash-merge PR title) using conventional commit types: `fix` → patch, `feat` → minor, `BREAKING CHANGE` or `!` → major.
- **FR-007**: On a version bump, the workflow MUST:
  - Update the version number in `pyproject.toml` using the semantic versioning tool
  - Append a changelog entry to CHANGELOG.md using the merge commit message content
  - Create a PR containing the version and changelog changes, with `[skip ci]` in the commit message to prevent re-triggering the release workflow
  - Auto-merge the PR via squash merge
  - Create a git tag `vX.Y.Z` from the merged result
  - Create a GitHub Release with the changelog entry as release notes
- **FR-008**: The workflow MUST include the PR description body in release notes to capture migration notes, usage guidance, and breaking change details.
- **FR-009**: The workflow MUST support `workflow_dispatch` (manual trigger) as an escape hatch for cases where GitHub suppresses automatic workflow triggers.
- **FR-010**: The project MUST create a CHANGELOG.md file at the repository root following the Conventional Commits changelog format.
- **FR-011**: Non-user-facing commit types (`chore`, `docs`, `ci`, `test`, `refactor`, `style`, `build`) MUST NOT trigger a version bump but SHOULD still generate changelog entries.
- **FR-012**: A safety-net auto-bump workflow SHOULD detect source code changes landing on main without a version bump and automatically open a patch-bump PR.
- **FR-013**: Local commit message format enforcement SHOULD be applied so that non-conventional commits are caught before they are pushed to the remote repository.

### Agentic Requirements (Non-Functional)

- **AR-001 (Idempotency)**: All workflow steps MUST be safe to re-run. If a step has already been completed (e.g., tag exists, changelog entry exists), subsequent runs MUST detect this state and skip the completed step, not fail or duplicate.
- **AR-002 (Deterministic Verification)**: Each workflow component MUST produce deterministic output that an agent can verify with a simple script or API call. After the release workflow completes, an agent MUST be able to run `git tag --list 'v*'`, `grep 'version =' pyproject.toml`, `head -30 CHANGELOG.md`, and `gh release view vX.Y.Z` to confirm every required artifact exists.
- **AR-003 (Fail-Fast with Diagnostics)**: If a required precondition is not met (e.g., `BUMP_PAT` secret missing, git not in a clean state, tag already exists), the workflow MUST fail immediately with a specific diagnostic message that tells an agent exactly what to fix and how.
- **AR-004 (No Silent Degradation)**: The workflow MUST NOT silently skip steps. Every decision (skip version bump, skip release, skip changelog update) MUST be explicitly logged with the reason and a clear action for the agent if intervention is needed.
- **AR-005 (Graceful Degradation Path)**: If the workflow encounters a non-critical failure (e.g., PR description fetch fails, changelog format is unexpected), it MUST complete the remaining steps and report the partial failure, not abort the entire release. Only critical failures (tag collision, broken pyproject.toml) should abort.
- **AR-006 (Agent-Detectable State)**: All state transitions (version bumped, tag created, release published) MUST be reflected in artifacts that an agent can inspect without running the workflow again — git log, git tags, release API, and file contents in main.
- **AR-007 (Implementation Ordering)**: The implementer MUST follow this dependency order:
  1. Commitizen config (FR-001–FR-004, FR-010) — no CI dependencies
  2. Local enforcement (FR-013) — depends on #1
  3. Release workflow (FR-005–FR-009) — depends on #1: workflow uses commitizen CLI
  4. Auto-bump safety-net (FR-012) — depends on #3: reuses version detection logic

### Key Entities *(include if feature involves data)*

- **Version String**: A semantic version (`X.Y.Z`) stored in `pyproject.toml` under `[project].version`. Acts as the single source of truth for releases and is read/written by Commitizen tooling.
- **CHANGELOG.md**: A markdown file at the repository root documenting all notable changes, organized by version with Conventional Commits section labels (`feat`, `fix`, `perf`, `refactor`, `chore`, `docs`, etc.).
- **Git Tag**: A lightweight tag (`vX.Y.Z`) created for each release, providing a stable reference point for the exact state of the codebase at each release.
- **GitHub Release**: A published release object in the GitHub UI that includes the tag, release notes (changelog content), and optional build artifacts.
- **PR Metadata**: Pull request title and description body used by the release workflow to determine the version bump type and enrich release notes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every pull request merged to main with a conventional commit title produces a version bump, changelog entry, git tag, and GitHub Release within 5 minutes of merge — without any manual intervention.
- **SC-002**: The CHANGELOG.md file is always up-to-date with the current release within the repository — no manual changelog editing required after a merge.
- **SC-003**: A new contributor can make their first conventional commit on their first day using the project's commit tooling without reading documentation beyond a brief setup note.
- **SC-004**: The system handles the "concurrent merge" scenario — two PRs merged within seconds of each other — without producing duplicate tags or corrupted changelog entries (at least one of the two merges produces a valid release).
- **SC-005**: Release notes for each version contain human-readable descriptions of changes organized by type (features, fixes, performance), automatically extracted from the merge commit message and PR description.
- **SC-006 (Agent Verifiability)**: An AI agent (or any automated system) can verify the health of the release pipeline by running 4 commands: `git tag --list 'v*' | tail -3` (tags exist), `grep '^version =' pyproject.toml` (version matches latest tag), `head -5 CHANGELOG.md` (changelog populated), and `gh release view $(git tag --list 'v*' | tail -1) --json name,body,tagName` (GitHub Release exists and matches tag). All 4 commands must succeed and produce consistent output.

## Assumptions

- **Assumption**: The project repository is hosted on GitHub. The release workflow uses GitHub Actions and GitHub Releases API. If the repo moves to a different platform, the CI/CD pipeline would need refactoring.
- **Assumption**: Pull requests to main are merged via **squash merge**, where the PR title becomes the squash-merge commit message. The release workflow parses the merge commit message to determine the conventional commit type.
- **Assumption**: Version is stored in `pyproject.toml` under `[project].version` (PEP 621), which is already the case. No separate version file is needed.
- **Assumption**: Only GitHub Releases are created — PyPI publishing is out of scope for this feature. If PyPI publishing is needed later, it can be added as a post-release workflow step.
- **Assumption**: The release workflow uses the built-in `GITHUB_TOKEN` for checkout and release-creation steps, with a fine-grained PAT (`BUMP_PAT`) for the auto-merge PR creation step (to satisfy branch protection rules that require CI checks on PRs). The `BUMP_PAT` must have `Contents: write`, `Pull requests: write`, and `Workflows: write` permissions on the repository. The version bump commit is delivered via an auto-merge PR (not direct push) to avoid triggering the release workflow again and to respect branch protection.
- **Dependency**: Requires Commitizen (`commitizen` Python package) as a project dependency, added to the `dev` optional-dependencies group in `pyproject.toml`.
- **Dependency**: Requires GitHub Actions enabled on the repository with sufficient permissions for contents:write and pull-requests:write.
- **Reference patterns**: The following local repositories were consulted as reference implementations for the spec. An implementing agent MUST read these files before writing any code:
  - `~/Workbench/Repositories/oldgrowth/.cz.toml` — Commitizen TOML config (primary config reference)
  - `~/Workbench/Repositories/oldgrowth/.github/workflows/release.yml` — Full release workflow with version detection, changelog extraction, GitHub Release creation, and the `gh release create --notes-file` pattern (read lines 1–70 for the version-check pattern, lines 962–1068 for the release-publish pattern)
  - `~/Workbench/Repositories/oldgrowth/.github/workflows/auto-bump.yml` — Safety-net auto-bump workflow with patch detection, changelog insertion, and auto-merge PR creation
  - `~/Workbench/Repositories/oldgrowth/CHANGELOG.md` — Conventional Commits changelog format (read lines 1–20 for the header template)
  - `~/Workbench/Repositories/concourse/pyproject.toml` and `~/Workbench/Repositories/mlx-lm-server/pyproject.toml` — Python-specific `[tool.commitizen]` examples using PEP 621 version provider

## Agent-First Implementation Guidance

This section provides explicit instructions for AI agents implementing this specification. Each block maps to a specific implementation step.

### Phase 1 — Commitizen Configuration (FR-001–FR-004, FR-010)

**Before writing any code, read these reference files:**
- `~/Workbench/Repositories/oldgrowth/.cz.toml` — Commitizen TOML config structure
- `~/Workbench/Repositories/concourse/pyproject.toml` — Python-specific `[tool.commitizen]` integration
- Existing `pyproject.toml` in the project root — current version `0.1.0`, PEP 621 `[project]` section

**What to create/update:**
1. Add `[tool.commitizen]` section to `pyproject.toml` with:
   - `name = "cz_conventional_commits"`
   - `version_scheme = "semver"`
   - `tag_format = "v$version"`
   - `version_provider = "pep621"` (reads version from `[project].version`)
   - `update_changelog_on_bump = true`
   - `changelog_incremental = true`
   - `changelog_file = "CHANGELOG.md"`
2. Add `commitizen` to `[project.optional-dependencies].dev` in `pyproject.toml`
3. Create `CHANGELOG.md` at root with the header template from `oldgrowth/CHANGELOG.md`
4. Run `cz bump --dry-run` to validate config parses

**Verification signals (agent runs these):**
- `cz version` exits 0 and shows commitizen version ✓
- `python -c "import tomllib; d = tomllib.load(open('pyproject.toml','rb')); assert 'commitizen' in d.get('tool',{}) or 'cz' in d.get('tool',{})"` passes ✓
- `cz check --rev-range HEAD~1..HEAD 2>&1 || true` shows valid format check ✓

### Phase 2 — Local Enforcement (FR-013)

**Before writing any code, check:**
- Whether the project already has `pre-commit` configured (check `.pre-commit-config.yaml`)
- Whether there are existing git hooks in `.git/hooks/`

**What to create/update:**
- Either a `pre-commit` hook config OR a `.git-hooks/commit-msg` script that runs `cz check --commit-msg-file $1`
- Prefer `pre-commit` with `commitizen` hook if pre-commit is already in use

**Verification signals:**
- Create a test commit with invalid format → rejected with helpful message ✓
- Create a test commit with valid format → accepted ✓

### Phase 3 — Release Workflow (FR-005–FR-009)

**Before writing code, read these reference files:**
- `~/Workbench/Repositories/oldgrowth/.github/workflows/release.yml` — especially:
  - Lines 1–40: workflow triggers and permissions
  - Lines 53–96: `check-version` job (version detection pattern)
  - Lines 962–1068: release publish step (changelog extraction + `gh release create` pattern)
- Existing `pyproject.toml` — note the `[project].version = "0.1.0"` format

**What to create:**
1. `.github/workflows/release.yml` with:
   - Trigger: `push` to `main` (no path filter — all merges checked for version change)
   - `workflow_dispatch` as escape hatch
   - `permissions: contents: write, pull-requests: write`
   - `concurrency: group: release, cancel-in-progress: false`
   - Jobs:
     - `check-version`: Reads version from `pyproject.toml`, compares with parent commit, outputs `version_changed` and `version`
     - `bump-and-release` (depends on `check-version`): Runs `cz bump --changelog`, creates a branch with the bump commit, opens a PR with `[skip ci]` in the commit message, auto-merges via `gh pr merge --auto --squash`, then creates tag `vVERSION` and GitHub Release via `gh release create`
   - PR description fetch: Use `gh pr view --json body --jq '.body'` on the merge commit to get PR description

**Key implementation details for agent:**
- Version extraction from `pyproject.toml`: Use `grep '^version =' pyproject.toml | sed 's/version = "\(.*\)"/\1/'`
- Version comparison: `git show HEAD^:pyproject.toml | grep '^version =' | sed 's/version = "\(.*\)"/\1/'`
- Determining bump type from conventional commit: Parse the merge commit message for `BREAKING CHANGE`, `feat:`, `fix:` prefixes
- `cz bump` with explicit level: `cz bump --yes --changelog --increment {MAJOR|MINOR|PATCH}`
- Changelog extraction for release notes: `awk "/^## \[${VERSION}\]/,/^## \[/" CHANGELOG.md`
- Tag and release: `git tag v${VERSION}` + `git push origin v${VERSION}` + `gh release create v${VERSION} --notes-file release-notes.md`
- PR description fetch: `gh pr list --state merged --head <branch> --json body --jq '.[0].body'`
- Token strategy: `GITHUB_TOKEN` for checkout/tag push/release create; `BUMP_PAT` for the auto-merge bump PR. Bump commit message includes `[skip ci]` to prevent loop.

### Phase 4 — Auto-Bump Safety-Net (FR-012)

**Before writing code, read:**
- `~/Workbench/Repositories/oldgrowth/.github/workflows/auto-bump.yml` — full auto-bump workflow

**What to create:**
1. `.github/workflows/auto-bump.yml` with:
   - Trigger: `push` to `main` on paths matching `anvil/**` (source code), excluding `CHANGELOG.md` and `.github/**`
   - `workflow_dispatch` as escape hatch
   - Job checks if version in `pyproject.toml` changed vs parent commit
   - If no change: opens a PR bumping patch version
   - PR body explains this was an automated safety-net bump

**Key implementation details:**
- Same version extraction logic as release workflow (reuse pattern)
- Use `BUMP_PAT` for PR creation (GITHUB_TOKEN PRs don't trigger CI)
- Patch bump: increment `X.Y.Z` to `X.Y.(Z+1)` in pyproject.toml
- Changelog entry: prepend `## [NEW_VERSION] — (date)` with "### fix\n- Automated patch bump" entry

### Agentic Checklist (Implementer's Tracker)

During implementation, the agent MUST verify each item and mark completion:

- [ ] `pyproject.toml` has `[tool.commitizen]` section
- [ ] `commitizen` in dev deps
- [ ] `cz bump --dry-run` exits 0
- [ ] `cz check` rejects invalid commit messages
- [ ] `CHANGELOG.md` exists with header
- [ ] `.github/workflows/release.yml` created and parses as valid YAML
- [ ] `.github/workflows/release.yml` reads version from pyproject.toml
- [ ] `.github/workflows/release.yml` compares with parent commit version
- [ ] `.github/workflows/release.yml` supports workflow_dispatch
- [ ] `.github/workflows/release.yml` has concurrency group
- [ ] `.github/workflows/release.yml` creates git tag vX.Y.Z
- [ ] `.github/workflows/release.yml` creates GitHub Release
- [ ] `.github/workflows/release.yml` fetches PR description
- [ ] `pyproject.toml` did not lose any existing config during edits
- [ ] `git commit --allow-empty -m "test: validate conventional commit format"` (via hook) is accepted
- [ ] `cz bump --dry-run --increment patch` shows expected version increment
- [ ] LSP diagnostics clean on all changed files
- [ ] `make lint` passes on all changed files

(The agent should verify each item in order; do not proceed to Phase 2 until all Phase 1 items pass.)