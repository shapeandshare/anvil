# Feature Specification: Raise Coverage Threshold (Ratcheting)

**Feature Branch**: `opencode/witty-forest`  
**Created**: 2026-07-18  
**Status**: Draft  
**Priority**: P1  
**Input**: Codebase review finding #075 — `pyproject.toml:203` has `fail_under = 23`, meaning only 23% coverage is required to pass. The docs/AGENTS.md mention ~41% current coverage. Article IV (TDD Mandatory) mandates a ratcheting baseline that may only increase.

## User Scenarios & Testing

### User Story 1 - Coverage threshold reflects actual coverage (Priority: P1)

The enforced coverage `fail_under` matches the current measured coverage level, implementing a ratcheting baseline that only moves upward.

**Why this priority**: The gap between `fail_under=23` and actual ~41% means coverage can drop by 18 points without failing CI. The Constitution (Article IV) explicitly requires the threshold to be the current measured level and that it may only increase.

**Independent Test**: Running `make test` currently reports ~41% coverage. After setting `fail_under` to match, the same command still passes.

**Acceptance Scenarios**:

1. **Given** `fail_under` is set to `23`, **When** coverage is measured at `41`, **Then** the threshold should be updated to `41` (or the exact current value).
2. **Given** `fail_under` is set to the current coverage level, **When** new code is added without tests, **Then** coverage drops and the build fails.

---

### User Story 2 - Coverage trend is tracked (Priority: P2)

Coverage is measured and reported on every CI run, with historical tracking showing the trend.

**Why this priority**: Ratcheting requires knowing the current coverage. Without tracking, coverage can drift downward and no one notices until it's too late.

**Independent Test**: A CI run's output includes the coverage percentage and a delta from the previous run.

**Acceptance Scenarios**:

1. **Given** `make test` runs, **When** it completes, **Then** the output includes `TOTAL` coverage percentage (already done via `--cov-report=term-missing`).

### Edge Cases

- What if coverage legitimately drops due to refactoring (e.g., removing dead code reduces numerator)? The threshold should not penalize legitimate simplification.
- What about migration files and generated code that are excluded from coverage?

## Requirements

### Functional Requirements

- **FR-001**: The `fail_under` value in `pyproject.toml:203` MUST be updated to match the current measured coverage level (rounded down to the nearest integer).
- **FR-002**: The `fail_under` value MUST only increase — lowering it requires explicit, recorded approval (per Constitution Article IV).
- **FR-003**: A CI gate MUST verify that coverage has not dropped below `fail_under` (already enforced by pytest-cov).
- **FR-004**: Coverage MUST be measured excluding migration files and generated code (already configured).
- **FR-005**: A process MUST be documented for updating `fail_under` when coverage increases (e.g., include in PR template or CONTRIBUTING.md).

### Key Entities

- **pyproject.toml**: `[tool.coverage.report] fail_under = <new_value>`
- **CI pipeline**: Already runs `pytest --cov=anvil --cov-report=term-missing`

## Success Criteria

### Measurable Outcomes

- **SC-001**: `fail_under` increased from 23 to current measured coverage (expected ~41 or higher).
- **SC-002**: `make test` passes with the new threshold.
- **SC-003**: The ratcheting policy is documented in CONTRIBUTING.md or AGENTS.md.

## Assumptions

- Current coverage is approximately 41% (as stated in AGENTS.md and ARCHITECTURE.md). The exact value must be verified by running `make test` before setting the threshold.
- Coverage is measured meaningfully — the metric accounts for the complexity of what's tested, not just line count.
