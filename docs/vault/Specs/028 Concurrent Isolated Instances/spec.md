---
title: 'Feature Specification: Concurrent Isolated Instances'
type: spec
tags:
  - type/spec
  - domain/operations
  - domain/infrastructure
spec-refs:
  - docs/vault/Specs/028 Concurrent Isolated Instances/
status: draft
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - 028 Concurrent Isolated Instances
---

# Feature Specification: Concurrent Isolated Instances

**Feature Branch**: `028-concurrent-isolated-instances`
**Created**: 2026-06-27
**Status**: Draft
**Input**: User description: "as a coding agent I want to be able to run stand-alone instances of the software stack concurrently — storage and network isolation, I want to be able to target these instances independent of the states of the other agents or processes running; this means written data must also be isolated. We need the application stack itself to support this level of configuration/reconfiguration and also be able to expose CRUD operations on this config in the UI. As a human user I want to use the UI to make install/config-level changes as much as possible and then manually or automatically restart services afterwards to make the changes take effect."

## Clarifications

### Session 2026-06-27

- Q: How should an instance's network ports be assigned at create time? → A: Auto-allocate free ports by default, with optional explicit override (caller may pin specific ports).
- Q: How many concurrent isolated instances must one host support? → A: Small scale — up to ~10 concurrent instances per host (design for ~10, not for moderate/unbounded fleets).
- Q: How is an instance identified, and what is the uniqueness rule? → A: The caller provides a required, unique name at create time; that name IS the instance identifier, and the registry rejects duplicate names.
- Q: Should instance lifecycle and config-change operations be audited? → A: Yes — audit BOTH instance lifecycle (create/start/stop/restart/destroy) and configuration changes, reusing the existing audit infrastructure (no new audit subsystem).
- Q: When an instance is destroyed, what happens to its workspace data by default? → A: Delete the workspace data by default; an explicit flag is required to KEEP it. (Because the default is destructive, destroy MUST require explicit confirmation.)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run two fully isolated instances side by side (Priority: P1)

As a coding agent, I want to launch a stand-alone instance of the entire application stack bound to its own ports with its own isolated storage and database, so that I can run a second (third, Nth) instance concurrently without either instance reading, writing, or corrupting the other's data — even if the other instance is mid-task, restarting, or crashed.

**Why this priority**: This is the foundational capability. Without true storage + network isolation, nothing else in the feature is safe to use. A single isolated, independently-targetable instance is the MVP that delivers the core value: agents working in parallel without interference.

**Independent Test**: Can be fully tested by creating two instances rooted at two different workspace directories with two different port sets, starting both, writing distinct data into each (a dataset, a trained model, an experiment), and confirming that each instance sees only its own data and that stopping or crashing one instance has zero effect on the other.

**Acceptance Scenarios**:

1. **Given** no instances are running, **When** an agent creates and starts an instance rooted at workspace A on its assigned ports, **Then** the instance comes up healthy and is reachable at its own base URL, with its database, file storage, model artifacts, experiment tracking store, and logs all located under workspace A.
2. **Given** instance A is running and serving requests, **When** an agent creates and starts a second instance rooted at workspace B on a different port set, **Then** instance B comes up healthy alongside A, and data written to B (datasets, models, experiments) is never visible from A and vice-versa.
3. **Given** both instances are running, **When** instance A is stopped, killed, or crashes mid-operation, **Then** instance B continues serving normally with no data corruption, no port conflict, and no dependency on A's state.
4. **Given** an agent has the base URL of a specific instance, **When** it issues requests to that instance, **Then** the responses reflect only that instance's isolated state, independent of every other instance's lifecycle.

---

### User Story 2 - View and edit an instance's configuration in the UI (Priority: P1)

As a human user, I want to open the running instance's UI and perform CRUD operations on its configuration — view current settings, change values such as ports, storage paths, device, MLflow settings, rate limits, and quotas — so that I can make install/config-level changes from the UI instead of hand-editing files or environment variables.

**Why this priority**: The user explicitly wants config managed "in the UI as much as possible." Pairing config CRUD (US2) with isolation (US1) is what makes an instance both isolated **and** operable by a human without leaving the app. P1 because the request treats UI-driven config as a primary goal, not a nice-to-have.

**Independent Test**: Can be fully tested by opening the instance's configuration page, reading the current effective config, changing one editable value, saving it, reloading the page, and confirming the new value persists for that instance only.

**Acceptance Scenarios**:

1. **Given** a running instance, **When** the user opens its configuration page, **Then** every configurable setting is listed with its current effective value and an indication of whether it came from a default, an environment variable, or a saved override.
2. **Given** the configuration page is open, **When** the user edits an editable setting and saves, **Then** the change is persisted to that instance's own configuration store and is reflected immediately on reload, without affecting any other instance.
3. **Given** a saved configuration override exists, **When** the user resets that setting, **Then** the override is removed and the value falls back to its environment/default source, shown clearly in the UI.
4. **Given** the user enters an invalid value (e.g. a non-numeric port, a port already in use by another known instance, or a workspace path that collides with another instance), **When** they attempt to save, **Then** the save is rejected with a clear, specific validation message and no partial/invalid config is persisted.

---

### User Story 3 - Apply config changes via restart, with clear "pending restart" status (Priority: P1)

As a human user, after I change configuration in the UI, I want the system to apply what it safely can without disruption (automatically restarting the experiment-tracking sidecar when its settings change) and to clearly mark the remaining boot-critical changes as "pending restart" so I know exactly what to do to make them take effect.

**Why this priority**: Saving config that silently does nothing is a trap. The user explicitly asked to "manually or automatically restart services afterwards to make the changes take effect." Honest apply/pending status is what closes the loop between editing and the change actually being live. P1 because US2 is incomplete without a truthful apply path.

**Independent Test**: Can be fully tested by changing an experiment-tracking setting (and confirming the sidecar auto-restarts and the change is live), then changing a boot-critical setting like the web port (and confirming the UI marks it "pending restart" and the change takes effect only after the documented restart action).

**Acceptance Scenarios**:

1. **Given** the user changes an experiment-tracking-sidecar setting, **When** they save, **Then** the system automatically restarts that sidecar for this instance and reports the change as "applied," without requiring a full restart of the instance.
2. **Given** the user changes a boot-critical setting (web port, database location, or workspace root), **When** they save, **Then** the UI persists the value and clearly marks it "pending restart," and the setting does not take effect until the instance is restarted.
3. **Given** one or more settings are "pending restart," **When** the user views the configuration page or operations area, **Then** a visible summary lists exactly which settings are pending and states the action required to apply them.
4. **Given** pending-restart settings exist, **When** the instance is restarted (via the documented manual action), **Then** on next boot the instance loads the saved configuration, the pending markers clear, and the new values are in effect.

---

### User Story 4 - Manage the instance lifecycle from the command line (Priority: P2)

As a coding agent, I want command-line operations to create, list, start, stop, restart, and destroy isolated instances, so that I can script parallel workflows and target instances programmatically without using the UI.

**Why this priority**: Agents are the primary driver of concurrency and need automation. CLI-first lifecycle management is what lets an agent spin up and tear down instances in scripts. P2 because a single instance (US1) plus UI config (US2/US3) already delivers value; full multi-instance lifecycle automation extends it.

**Independent Test**: Can be fully tested by running a CLI command to create an instance with a chosen workspace and ports, listing instances to confirm it appears with its status, starting it, confirming health, then stopping and destroying it and confirming it no longer appears.

**Acceptance Scenarios**:

1. **Given** the tool is installed, **When** the agent runs the create-instance command with a workspace directory and port set, **Then** an instance definition is registered and its workspace is initialized, and the command reports the instance identifier and assigned ports.
2. **Given** registered instances exist, **When** the agent runs the list command, **Then** each instance is shown with its identifier, workspace path, assigned ports, and current run status (running/stopped/unhealthy).
3. **Given** an instance is registered, **When** the agent runs start / stop / restart for it, **Then** that instance's processes change state accordingly while every other instance is unaffected.
4. **Given** a stopped instance, **When** the agent runs the destroy command, **Then** an explicit confirmation is required, the instance is removed from the registry, its workspace data is deleted by default (or preserved if the "keep" flag is supplied), and the command states clearly whether the data was deleted or preserved.

---

### User Story 5 - Prevent collisions between concurrent instances (Priority: P2)

As an operator running many instances on one host, I want the system to refuse configurations that would cause two instances to fight over the same ports or the same data directory, so that concurrency never silently corrupts data or fails confusingly.

**Why this priority**: Isolation guarantees are only real if the system actively prevents the two classic single-host failure modes — port reuse and shared data roots. P2 because basic isolation (US1) works for carefully-chosen distinct values, but collision prevention hardens it against operator/agent mistakes.

**Independent Test**: Can be fully tested by attempting to start a second instance on a port already bound by a running instance (rejected with a clear message), and attempting to point a second instance at a workspace already owned by a running instance (rejected with a clear message).

**Acceptance Scenarios**:

1. **Given** an instance is running on a given port set, **When** an agent or user attempts to start another instance whose web or tracking port overlaps, **Then** the start is rejected before binding, with a message identifying the conflicting port and the instance that holds it.
2. **Given** an instance owns a workspace directory, **When** another instance attempts to start using the same workspace root (or a nested overlap), **Then** the start is rejected with a message naming the conflicting workspace and owning instance.
3. **Given** a registry of instances, **When** an instance is starting, **Then** it acquires an exclusive lock on its workspace for the duration it runs, and releases it cleanly on stop (and stale locks from crashed instances are detectable and recoverable).

---

### Edge Cases

- **Stale workspace lock after a crash**: If an instance crashes without releasing its workspace lock, how is the lock reclaimed? → The lock records the owning process; on a start attempt, if the recorded process is no longer alive, the stale lock is reclaimed automatically; if it is alive, the start is refused.
- **Boot-critical change saved but never restarted**: A user changes the web port, saves, but never restarts. → The change remains "pending restart" indefinitely; the running instance keeps its current port; the UI continues to surface the pending state so the discrepancy is never silent.
- **Auto-restart of the tracking sidecar fails** (e.g. its new port is taken): → The instance reports the failed apply with a clear error, the prior sidecar state is preserved where possible, and the setting is surfaced as failed-to-apply rather than silently applied.
- **Editing the workspace root of a running instance**: → Treated as boot-critical and pending-restart; the running instance never relocates its data mid-flight. Relocating/moving existing data between workspaces is out of scope (see Assumptions).
- **Two agents create instances simultaneously and request the same port/workspace**: → The registry serializes registration; the second request is rejected with a collision message.
- **Destroying a running instance**: → Destroy requires the instance to be stopped first (or an explicit force that stops it), preventing removal of a live instance. Destroy deletes workspace data by default and requires explicit confirmation; a "keep" flag preserves the data while unregistering the instance.
- **A configurable value that the application reads only at process start** (e.g. database location): → It is classified boot-critical; the UI never claims it is hot-applied.
- **Invalid persisted config on boot** (e.g. a saved port that is now occupied, or a malformed value): → The instance fails fast at startup with a clear, actionable error naming the offending setting rather than starting in an inconsistent state.
- **Default/first-run instance**: → Running the stack with no explicit instance configuration behaves as a single default instance rooted at the conventional workspace, preserving today's out-of-the-box experience.
- **A write location that still resolves relative to the process working directory** instead of the instance workspace: → This is a defect; the isolation audit (FR-018) requires every persistent write to derive from the instance workspace root.

## Requirements *(mandatory)*

### Functional Requirements

#### Isolation (network + storage + data)

- **FR-001**: The system MUST support running multiple instances of the full application stack concurrently on a single host as separate operating-system process groups, each rooted at its own dedicated workspace directory.
- **FR-002**: Each instance MUST bind its web interface and its experiment-tracking sidecar to its own configurable network ports, with no shared ports between instances.
- **FR-003**: Each instance MUST store ALL of its persistent written data under its own workspace root, including (at minimum): the application database, uploaded/curated datasets, general file storage, trained model artifacts, the versioned content repository, experiment-tracking store and artifacts, the persisted API key, backups, and logs.
- **FR-004**: An instance MUST be independently targetable by its base URL such that requests to it reflect only its own isolated state, regardless of whether any other instance is running, restarting, or crashed.
- **FR-005**: The lifecycle state of one instance (running, stopped, crashed, restarting) MUST have no effect on the data integrity or availability of any other instance.
- **FR-006**: No instance MUST be able to read or write another instance's persistent data through normal operation.

#### Configurability of the stack

- **FR-007**: The application stack MUST expose a single, well-defined set of configurable settings that govern an instance's network bindings, storage/data locations (derivable from the workspace root), experiment-tracking settings, compute device selection, request rate limits, and operational quotas.
- **FR-008**: Every persistent data location used by an instance MUST be derivable from that instance's workspace root (with optional per-location overrides), so that selecting one workspace fully determines where that instance writes.
- **FR-009**: An instance's effective configuration MUST be resolved from a defined precedence order: saved per-instance overrides take precedence over environment-provided values, which take precedence over built-in defaults.

#### UI CRUD on configuration

- **FR-010**: The system MUST provide a configuration page in each instance's web UI that lists every configurable setting with its current effective value and the source of that value (default, environment, or saved override).
- **FR-011**: Users MUST be able to create/update a configuration override for an editable setting from the UI, persisting it to that instance's own configuration store.
- **FR-012**: Users MUST be able to read the full current configuration and delete (reset) an individual override from the UI, returning the setting to its environment/default value.
- **FR-013**: The system MUST validate configuration edits before persisting them, rejecting invalid values (malformed types, out-of-range values, ports known to conflict with another instance, or workspace paths that collide with another instance) with a clear, specific message and persisting no partial/invalid configuration.
- **FR-014**: Configuration changes made in one instance's UI MUST affect only that instance and never alter another instance's configuration.

#### Applying changes (restart model)

- **FR-015**: The system MUST classify each configurable setting as either "applies after restart" (boot-critical) or "applies without a full instance restart," and MUST expose this classification in the UI.
- **FR-016**: When a setting that governs the experiment-tracking sidecar changes, the system MUST automatically restart that sidecar for the affected instance to apply the change, and MUST report the result (applied or failed-to-apply) clearly.
- **FR-017**: When a boot-critical setting changes (including web port, database location, and workspace root), the system MUST persist the value, mark it "pending restart," continue running with the prior value until restarted, and surface a visible summary of all pending-restart settings together with the action required to apply them. The setting MUST take effect on the next instance start, at which point its pending marker clears.

#### Concurrency safety

- **FR-018**: The system MUST guarantee, by audit, that there are no remaining persistent write locations that resolve outside the instance workspace root (e.g. relative to the ambient process working directory) — every write location enumerated in FR-003 MUST derive from the instance workspace.
- **FR-019**: The system MUST prevent port collisions: before an instance binds, it MUST verify its configured web and tracking ports are not already in use by a known running instance, and MUST refuse to start with a clear message identifying the conflicting port and owning instance otherwise.
- **FR-019a**: At create time the system MUST auto-allocate free network ports for the instance's web interface and tracking sidecar by default (selecting unused ports), AND MUST allow the caller to optionally pin explicit ports instead. When explicit ports are supplied, the collision check (FR-019) applies to the supplied values; when auto-allocated, the system MUST select ports already verified free.
- **FR-020**: The system MUST prevent workspace/data-path collisions: it MUST refuse to start an instance whose workspace root is the same as, or overlaps with, a workspace owned by another running instance, with a clear message identifying the conflict.
- **FR-021**: A running instance MUST hold an exclusive lock on its workspace for its lifetime, release it on clean stop, and the system MUST detect and safely reclaim a stale lock left by a crashed instance (by verifying the recorded owner is no longer alive).

#### CLI instance lifecycle (agent automation)

- **FR-022**: The system MUST provide command-line operations to create, list, start, stop, restart, and destroy instances.
- **FR-023**: The create operation MUST accept (at minimum) a required unique instance name, a workspace directory, and an OPTIONAL port set (ports are auto-allocated when omitted, per FR-019a), initialize the workspace, register the instance, and report the instance name and the ports actually assigned.
- **FR-023a**: The caller-provided instance name MUST serve as the instance's identifier and MUST be unique within the registry; the create operation MUST reject a name that is already registered with a clear message, and MUST validate the name against a defined format (non-empty, filesystem/URL-safe).
- **FR-024**: The list operation MUST enumerate registered instances with identifier, workspace path, assigned ports, and current run status.
- **FR-025**: Start/stop/restart operations MUST act on a single named instance and MUST NOT affect any other instance.
- **FR-026**: The destroy operation MUST require the instance to be stopped first (or an explicit force flag that stops it) and MUST remove the instance from the registry. By default it MUST DELETE the instance's workspace data; an explicit "keep" flag MUST preserve the workspace on disk while still unregistering the instance. Because the default is destructive, destroy MUST require explicit confirmation (typed confirmation or an explicit confirmation flag) before deleting data, and MUST clearly state in its result whether the workspace data was deleted or preserved.

#### Registry / discovery

- **FR-027**: The system MUST maintain a registry of instances recording the unique name (identifier), workspace path, assigned ports, and status, sufficient for an agent to discover and target instances independently of one another.
- **FR-028**: The default (no explicit-instance) way of running the stack MUST continue to work as a single instance rooted at the conventional workspace, preserving the current out-of-the-box experience.

#### Observability / audit

- **FR-029**: The system MUST emit an audit-log entry (via the existing audit infrastructure) for each instance lifecycle operation (create, start, stop, restart, destroy) and for each configuration change (override created/updated/reset), capturing at minimum the operation type, target instance name, the setting changed (for config operations), and a timestamp.

### Key Entities *(include if feature involves data)*

- **Instance**: An independently runnable, isolated deployment of the full application stack. Attributes: name (caller-provided, required, unique within the registry — serves as the identifier), workspace root path, assigned web port, assigned tracking port, run status (running/stopped/unhealthy), owning-process reference (for lock validation).
- **Workspace**: The single root directory under which all of an instance's persistent data lives (database, datasets, file storage, model artifacts, content repository, tracking store, persisted API key, backups, logs). Exactly one instance may own a given workspace at a time.
- **InstanceConfig**: The per-instance set of configuration overrides edited via the UI/CLI. Stored in the instance's own configuration store; layered over environment values and built-in defaults. Each setting carries: key, value, source (default/env/override), and apply-class (boot-critical vs. applies-without-restart).
- **WorkspaceLock**: An exclusivity marker held by a running instance over its workspace, recording the owning process so stale locks from crashed instances can be detected and reclaimed.
- **InstanceRegistry**: The collection of known instance definitions and their live status, used for listing, discovery, and collision detection (ports and workspaces).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Two instances can run concurrently on one host, and data written exclusively to one instance is never observable from the other in 100% of tests.
- **SC-002**: Stopping, killing, or crashing one instance leaves every other running instance fully available and uncorrupted in 100% of tests.
- **SC-003**: A user can view an instance's full configuration and change a setting from the UI in under 1 minute, and the change persists for that instance only.
- **SC-004**: Every setting saved in the UI is either applied automatically (with a confirming status) or clearly marked "pending restart" — there are zero cases where a saved setting silently has no effect and no indication is shown.
- **SC-005**: An agent can create, start, confirm-healthy, stop, and destroy an isolated instance entirely from the command line without using the UI.
- **SC-006**: 100% of attempts to start an instance with a port or workspace that conflicts with a running instance are rejected before any binding or data write, with a message naming the specific conflict.
- **SC-007**: An audit confirms that 100% of an instance's persistent write locations resolve under its workspace root, with zero writes escaping to the ambient working directory.
- **SC-008**: Running the stack with no explicit instance configuration produces a working single default instance with the same first-run experience as before this feature.
- **SC-009**: At least 10 isolated instances can be registered and run concurrently on a single host with zero cross-contamination and zero port conflicts; the design is not required to scale beyond ~10 per host.

## Assumptions

- **Single host, separate processes**: Instances are separate OS process groups on one host (not containers and not a single multiplexing process). Container-per-instance and in-process multi-tenancy are out of scope for this feature.
- **Small scale**: The feature targets up to ~10 concurrent instances on a single host (typical multi-agent sandboxing). Port-range allocation, the registry, and resource planning are sized for this; scaling to moderate/unbounded fleets is out of scope.
- **Per-instance configuration store**: Each instance's editable configuration is persisted in that instance's own application database, layered over environment values and built-in defaults. Because the database is itself per-instance, configuration is naturally isolated.
- **Restart model**: Most apply work is "save then restart." The experiment-tracking sidecar (already independently manageable today) is auto-restarted when its settings change. Boot-critical settings (web port, database location, workspace root) are marked "pending restart" and applied by the user via the documented restart action. No speculative hot-reload machinery is built for settings that are read only at process start.
- **CLI-first lifecycle, UI-for-config**: Instance creation/listing/targeting/destruction is driven from the command line for agent automation; the per-instance UI focuses on CRUD of the configuration of the instance it is serving. A full instance-management UI is out of scope for this feature.
- **Workspace = single root**: All persistent data for an instance derives from one workspace root, so choosing a workspace fully determines isolation. Existing environment-variable overrides for individual locations remain supported for advanced use.
- **Data relocation out of scope**: Changing an instance's workspace root applies to future writes after restart; migrating or copying existing data from an old workspace to a new one is out of scope.
- **Collision scope**: Collision prevention covers the two single-host failure modes — port reuse and shared/overlapping workspace roots — among instances known to the registry on the same host. Cross-host coordination is out of scope.
- **Security boundary unchanged**: Isolation is filesystem- and port-based on a trusted single host; instances inherit the host's filesystem permissions. A hardened security boundary between mutually distrusting instances is out of scope.
- **Reuses existing infrastructure**: The feature builds on the existing operations/service-management surface, the existing per-instance database and repository layering, the existing audit-event infrastructure (reused for lifecycle + config-change auditing per FR-029), and the existing experiment-tracking sidecar management rather than introducing a new supervisor, audit, or orchestration subsystem.
- **Default experience preserved**: The conventional single-instance, zero-config run path continues to work unchanged for users who never opt into multiple instances.
