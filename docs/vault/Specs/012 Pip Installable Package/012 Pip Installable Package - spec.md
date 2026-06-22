---
title: 012 Pip Installable Package - spec
type: spec
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/012 Pip Installable Package/
related:
  - '[[012 Pip Installable Package]]'
created: ~
updated: ~
---
# Feature Specification: Pip-Installable Package

**Feature Branch**: `012-pip-installable-package`  
**Created**: 2026-06-18  
**Status**: Draft  
**Input**: User description: "anvil must be pip installable by a user"

## Clarifications

### Session 2026-06-18

- **Distribution channel**: Public-facing distribution (PyPI or any external index) is **out of scope** for this feature and will be handled in a later spec. This feature delivers a **locally buildable, installable artifact** that carries all runtime prerequisites.
- **Install name conflict**: Because there is no public-index publish in this feature, the artifact keeps the `anvil` name; resolving any public-index naming conflict is deferred to the later distribution spec.
- **Validation strategy**: Correctness is proven by installing the built artifact into a **clean, isolated container environment** (Dockerfile), bringing it online locally via **container orchestration (docker compose)**, and running **system tests** against the running instance.
- **Test depth**: "Just enough" to validate a functional end product — smoke/system-level coverage of install success, server startup, primary page reachability, and command-line tools. Full test suites and CI pipelines are **out of scope**; enrichment is covered by other specs.
- Q: How should the container validate the install (the existing Dockerfile copies the source tree and runs `make setup`, which never exercises a built artifact)? → A: Build the wheel, then `pip install` it into a clean image containing no source tree, and run `anvil` from the installed package.
- Q: How should MLflow run in the docker compose validation environment, given it is currently an in-process subprocess on port 5001? → A: Single app container — MLflow stays in-process (current behavior); compose runs one anvil service with ports/volume. No separate MLflow service in this feature.
- Q: Is first-run demo/seed content part of the functional end product, given it currently lives outside the package and no-ops when installed? → A: Yes — bundle demo/seed content into the package so first-run auto-bootstrap works in the installed package; system tests verify demo content appears.
- Q: How should the runtime workspace (data/logs/mlruns) be handled across docker compose runs, given it affects whether tests exercise a fresh first-run? → A: Persistent named volume for normal local use, but the system tests MUST explicitly reset/teardown the workspace before each run so first-run init (auto-migration + demo bootstrap) is always exercised.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build a self-contained installable artifact (Priority: P1)

A maintainer runs a single build step and gets one distributable artifact for anvil. That artifact bundles all of anvil's code, all of its non-code runtime resources (UI assets, page templates, database schema/initialization, default/demo content), and declares every dependency required to run the base workbench — so that nothing from the original source tree is needed to run it.

**Why this priority**: Everything else depends on having a correct, self-contained artifact. If the build omits resources or under-declares dependencies, no downstream install or runtime test can succeed. This is the foundational slice.

**Independent Test**: Run the build, inspect the produced artifact, and confirm it contains the expected non-code resources and a complete dependency declaration — without needing the source checkout.

**Acceptance Scenarios**:

1. **Given** the anvil source tree, **When** the maintainer runs the documented build step, **Then** a single installable artifact is produced without errors.
2. **Given** the produced artifact, **When** its contents are inspected, **Then** all runtime non-code resources (UI assets, templates, schema/migrations, default/demo content) are present inside it.
3. **Given** the produced artifact, **When** its dependency declaration is inspected, **Then** every dependency required to run the base workbench is listed.

---

### User Story 2 - Install the artifact into a clean, isolated environment (Priority: P1)

A maintainer installs the built artifact into a clean container environment that contains only a supported runtime and none of anvil's source code. The install pulls in all required dependencies and produces a working installation, proving the artifact is genuinely self-contained.

**Why this priority**: A clean-room install is the definitive proof that the package delivers all prerequisites. Installing on top of a source checkout would mask missing files or dependencies; isolation is what makes the test meaningful. This is required for the core promise.

**Independent Test**: From a container image that has only a supported runtime, install the artifact, and confirm the install completes and anvil's console commands become available — with no source tree present.

**Acceptance Scenarios**:

1. **Given** a clean container image with only a supported runtime, **When** the artifact is installed, **Then** the install completes successfully and pulls in all required dependencies.
2. **Given** the install completed in the clean image, **When** anvil's console commands are invoked, **Then** they are present and execute.
3. **Given** the install attempt runs on an unsupported runtime version, **When** the install runs, **Then** it fails fast with a clear message stating the supported version range.

---

### User Story 3 - Bring the installed package online locally for testing (Priority: P1)

A maintainer uses local container orchestration (docker compose) to start the installed anvil from its container image, with the environment it needs to run (ports, runtime workspace for data/logs, any auxiliary services). The web workbench becomes reachable locally.

**Why this priority**: Installing is necessary but not sufficient — the artifact must actually run as a usable application in a realistic, reproducible environment. Bringing it online locally is the bridge between "installs" and "works." Required for the core promise.

**Independent Test**: Run the orchestration command, wait for startup, and confirm the workbench is reachable at the documented local address and serves its primary page.

**Acceptance Scenarios**:

1. **Given** the container image with anvil installed, **When** the maintainer brings it online with the orchestration command, **Then** the web workbench starts and becomes reachable at the documented local address.
2. **Given** the workbench is starting for the first time, **When** it initializes, **Then** the data store is created and initialized automatically with no separate setup step.
3. **Given** the workbench is running in the container, **When** runtime files (data, logs) are written, **Then** they are created in a predictable, documented location.
4. **Given** the maintainer stops the orchestration, **When** the stack is brought down, **Then** the instance shuts down cleanly.

---

### User Story 4 - Validate the running instance with system tests (Priority: P1)

A maintainer runs a focused set of system tests against the running, container-deployed anvil to confirm the end product is functional: the server responds, primary pages render with their assets, the data store initialized, and the command-line tools work. Passing these tests is the signal that the installable package is a functional end product.

**Why this priority**: This is the acceptance gate for the whole feature. Without an automated, repeatable check against the deployed instance, "it works" is just a manual claim. Required for the core promise.

**Independent Test**: With the instance online, run the system test command and confirm all checks pass against the live container.

**Acceptance Scenarios**:

1. **Given** anvil is running in the container, **When** the system tests run, **Then** they confirm the server is reachable and responds successfully.
2. **Given** anvil is running in the container, **When** the system tests exercise the primary web pages, **Then** each page renders with correct styling and templates (no missing assets).
3. **Given** anvil is running in the container, **When** the system tests invoke the command-line tools, **Then** each tool executes successfully.
4. **Given** anvil started fresh in the container, **When** the system tests inspect the data store, **Then** it is confirmed to have been created and initialized automatically.
5. **Given** any of the above checks fail, **When** the system tests complete, **Then** they report a clear, actionable failure indicating which aspect of install or runtime is broken.

---

### Edge Cases

- **Unsupported runtime**: Installing on an unsupported runtime version fails fast with a clear message stating the supported range, rather than producing a broken install.
- **Missing bundled resource**: If a required non-code resource is omitted from the artifact, the failure surfaces during the system tests (e.g., a page missing assets) with a clear signal, rather than passing silently.
- **Read-only / non-writable runtime workspace**: When anvil cannot create its data or log directories in the container, it surfaces a clear, actionable error instead of failing obscurely.
- **Port already in use**: When the configured local port is occupied, the failure message is clear and the maintainer is told how to change it.
- **Partial / interrupted build or install**: Re-running the build or install results in a clean, working result rather than a corrupted half-state.
- **Auxiliary services**: If anvil depends on auxiliary background services to be usable, the orchestrated environment starts them too; if one fails to start, the failure is clearly reported.
- **Stale container image**: Rebuilding the image after a code change produces an image reflecting the new artifact, not a cached older one.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST produce a single installable artifact for anvil via a documented build step, without requiring project-specific build tooling beyond what is documented.
- **FR-002**: The installable artifact MUST declare every dependency required for the base workbench to run, so that installing it pulls in all prerequisites with no manual dependency steps.
- **FR-003**: The installable artifact MUST include all non-code resources required at runtime (UI assets, page templates, database schema/migrations, and default/demo seed content), so it behaves identically to a source checkout for the supported workflows. In particular, database migrations and demo/seed content — which currently live outside the package and are resolved relative to the working directory — MUST be packaged so they resolve correctly from the installed package.
- **FR-003a**: On first launch of the installed package, anvil MUST auto-bootstrap its bundled demo/seed content (matching source-checkout behavior), and the system tests MUST verify that demo content is present.
- **FR-004**: anvil MUST be installable from the locally built artifact (no public or external package index required for this feature).
- **FR-005**: Installing the artifact into a clean, isolated environment that contains only a supported runtime MUST result in a working installation with all of anvil's console commands available and functional.
- **FR-006**: The install MUST fail fast with a clear, actionable message when attempted on an unsupported runtime version, rather than installing a non-working package.
- **FR-007**: A reproducible container image definition (Dockerfile) MUST install anvil by `pip install`-ing the built artifact into a clean base image that contains NO copy of the anvil source tree, so the image exercises a genuine package install (not a source checkout) and provisions the environment anvil needs to run.
- **FR-008**: A local orchestration definition (docker compose) MUST bring the installed anvil online locally as a single app service (with MLflow running in-process inside that container, consistent with current behavior), exposing the web port (8080) and the in-process MLflow port (5001) and provisioning required configuration (ports, runtime workspace).
- **FR-009**: After the artifact is installed, a user MUST be able to start the web workbench with a single documented command, and reach it at the documented local address.
- **FR-010**: On first launch from the installed package, anvil MUST initialize its data store automatically without requiring a separate setup command.
- **FR-011**: anvil MUST create its runtime files (data, logs, mlruns) in a predictable, documented location within the orchestrated environment, and MUST surface a clear error if it cannot.
- **FR-011a**: The orchestration MUST back the runtime workspace with a persistent named volume so state survives restarts for normal local use; the system tests MUST explicitly reset/teardown that workspace before a run so each test run exercises a fresh first-run (auto-migration + demo bootstrap).
- **FR-012**: A focused set of system tests MUST exist that runs against the running, container-deployed anvil and validates: server reachability, primary page rendering (with assets), data-store initialization, and command-line tool execution.
- **FR-013**: The system tests MUST produce a clear pass/fail result, where any failure identifies which aspect of install or runtime is broken.
- **FR-014**: The base install MUST remain lean — heavyweight, hardware-specific, or specialized dependencies MUST remain opt-in rather than included by default.
- **FR-015**: A maintainer MUST be able to determine the version of the built/installed artifact.

### Out of Scope (this feature)

- Publishing to a public or external package index, public-facing install names, and resolving any public-index naming conflict (deferred to a later distribution spec).
- Continuous integration / automated release pipelines.
- Exhaustive or full-coverage test suites (only enough system-level validation to prove a functional end product).
- Feature enrichment beyond a functional installable package (covered by other specs).

### Key Entities *(include if feature involves data)*

- **Installable artifact**: The single built, installable representation of anvil. Key attributes: a version identifier, a declared supported-runtime range, a complete required-dependency declaration, and bundled non-code runtime resources.
- **Container image**: A reproducible, isolated environment built from a definition that installs the artifact and provisions anvil's runtime needs.
- **Local orchestration stack**: The locally runnable composition that starts the installed anvil (and any required auxiliary services) and exposes the workbench for testing.
- **Runtime workspace**: The predictable location where the installed package stores its data store, logs, and generated content, created automatically on first use.
- **System test suite**: A focused set of checks executed against the running instance that gate the feature as a functional end product.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single documented build step produces one installable artifact, with zero manual file assembly required.
- **SC-002**: Installing the artifact into a clean isolated environment (only a supported runtime present) succeeds with zero manual dependency steps.
- **SC-003**: 100% of bundled non-code resources required at runtime are present in the artifact (verified by zero missing-asset failures during system tests).
- **SC-004**: A maintainer can bring anvil online locally from the installed artifact using a single orchestration command and reach the workbench in a browser.
- **SC-005**: First launch from the installed package initializes the data store automatically, with zero manual setup steps.
- **SC-006**: 100% of primary web pages render with correct styling and templates when served from the container-deployed instance.
- **SC-007**: 100% of documented command-line tools execute successfully against the container-deployed instance.
- **SC-008**: The system tests run against the running instance and return a single, unambiguous pass/fail result; on failure, the failing aspect (install vs. runtime vs. specific check) is identifiable.
- **SC-009**: A base install (without optional extras) excludes heavyweight/hardware-specific dependencies, verified by their absence in the resulting environment.
- **SC-010**: The full loop — build artifact → build image → bring online → system tests pass — can be executed locally by a maintainer from documented commands.

## Assumptions

- "Pip installable by a user" for this feature means an installable artifact built from source that a user (or container) installs with the standard Python installer — not a public-index release.
- "Usable after install" means the full web workbench launches via the existing console command(s); anvil is treated as an installable application, not merely an importable library.
- The supported-runtime range (Python 3.11+) and the existing optional capability sets (e.g., GPU, remote compute) carry forward unchanged.
- Auxiliary background services anvil currently manages (such as experiment tracking) start as part of the orchestrated launch experience, consistent with current behavior.
- The runtime workspace defaults to a directory within the orchestrated environment, consistent with current behavior.
- "System tests" are smoke/system-level checks sufficient to prove a functional end product; depth beyond that, plus CI and full suites, is intentionally deferred.
- Container tooling (a container engine and compose-style orchestration) is available in the local environment used to validate the package.
