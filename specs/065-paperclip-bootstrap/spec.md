# Feature Specification: Bootstrap Anvil into Paperclip

**Feature Branch**: `063-paperclip-bootstrap`  
**Created**: 2026-07-05  
**Status**: Draft  
**Input**: User description: "we need to bootstrap anvil into paperclip the same way we did conjure, see ../configure and ~/.paperclip"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run the seed script to bootstrap the Anvil company (Priority: P1)

As the operator, I want to run a single seed script that creates the Anvil company inside Paperclip, so that agents can start working on anvil's backlog without manual UI/CLI setup.

**Why this priority**: Without a seeded company, nothing in Paperclip exists — no agents, no projects, no tickets. This is the foundation everything else depends on.

**Independent Test**: Can be fully tested by running the seed script against a running Paperclip instance and verifying the company, goals, projects, agents, and tickets appear via `npx paperclipai company list`, `npx paperclipai agent list -C <companyId>`, etc.

**Acceptance Scenarios**:

1. **Given** Paperclip is running at `http://127.0.0.1:3100`, **When** the operator runs the seed script with no arguments, **Then** a Paperclip company named "Anvil" is created with the mission defined in the script.
2. **Given** the Anvil company exists, **When** the seed script completes, **Then** the company has at least one mission-level goal and one team-level goal.
3. **Given** the Anvil company exists, **When** the seed script completes, **Then** the company has at least two projects linked to goals.
4. **Given** the Anvil company exists, **When** the seed script completes, **Then** at least one agent exists with `adapterType: opencode_local` and cwd pointing to the anvil repository.
5. **Given** the Anvil company exists, **When** the seed script completes, **Then** at least one seed ticket exists and is assigned to an agent.
6. **Given** the seed script has already been run once, **When** it is run again, **Then** it detects the existing company and skips creation (idempotent) — printing a warning about existing goals/projects/agents.

---

### User Story 2 - Agents begin working on anvil backlog (Priority: P2)

As the operator, I want agents to start working on anvil's existing spec backlog and ongoing maintenance, so that development velocity increases through parallel agent work.

**Why this priority**: The point of Paperclip is autonomous agent work. Seeding is just setup — the real value starts when agents pick up tickets.

**Independent Test**: Can be tested by enabling a single agent's heartbeat, assigning it a ticket, and verifying it begins work (status change, comments, branch creation).

**Acceptance Scenarios**:

1. **Given** the Anvil company is seeded with agents, **When** the operator enables an agent's heartbeat in the Paperclip UI, **Then** the agent wakes, checks its inbox, and picks up an assigned ticket.
2. **Given** an agent is working on a ticket, **When** it completes its work, **Then** it creates a PR or branch, comments on the ticket with a status update, and moves the ticket to review.
3. **Given** an agent encounters a blocking issue, **When** it cannot proceed, **Then** it escalates via issue comments to the CEO agent or human operator.

---

### User Story 3 - Operator monitors agent work and costs (Priority: P3)

As the operator, I want to see what agents are doing and how much they cost, so that I can make informed decisions about staffing and budget.

**Why this priority**: Paperclip's value is trust-through-transparency. Without cost visibility, runaway spending is the #1 risk.

**Independent Test**: Can be tested by inspecting the Paperclip UI (Costs tab, Agents → Runs) after agents have been active.

**Acceptance Scenarios**:

1. **Given** an agent has completed at least one run, **When** the operator opens the Paperclip UI at `http://localhost:3100`, **Then** the operator can view the full transcript of any agent run.
2. **Given** budget has been configured on the company, **When** the operator navigates to the Costs page, **Then** spend is broken down by agent, project, and goal.

---

### Edge Cases

- What happens when Paperclip is not running when the seed script executes? The script should detect this and exit with a clear error message.
- What happens when the Paperclip instance has no remaining budget capacity? The company budget cap should be checked before creating new agents.
- What happens when the OpenRouter/LLM key is not configured? Agents won't be able to work — the seed script and agent setup should validate connectivity.
- How does the system handle a duplicate seed run? Goals, projects, and agents should not be duplicated — the existing company should be detected and re-seeding should be a no-op (with a warning).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A seed script (`anvil-seed.sh`) MUST exist that bootstraps the Anvil company inside a running Paperclip instance, following the same pattern as `conjure-seed.sh` (company → goals → projects → agents → tickets).
- **FR-002**: The seed script MUST create a Paperclip company named "Anvil" with a mission that reflects the project's purpose ("Train and experiment with LLMs from scratch — a pip-installable workbench with live training dashboards, MLflow tracking, and a polished web UI").
- **FR-003**: The seed script MUST create at least one mission-level goal and team-level goals underneath it.
- **FR-004**: The seed script MUST create at least two projects, each linked to a team-level goal.
- **FR-005**: The seed script MUST create at least two agents using the `opencode_local` adapter, with the anvil repository as their working directory.
- **FR-006**: The seed script MUST create agents with heartbeats DISABLED by default — the operator enables them deliberately.
- **FR-007**: The seed script MUST set a company-level hard budget cap.
- **FR-008**: The seed script MUST create at least one seed ticket per project, assigned to the appropriate agent.
- **FR-009**: The seed script MUST be idempotent — re-running detects the existing company and skips creation, with a clear warning that goals/projects/agents may be duplicated.
- **FR-010**: An `AGENTS.md` update or companion staffing plan SHOULD be created that documents the Paperclip agent structure (agents, roles, budgets, escalation paths, reserved powers).
- **FR-011**: The seed script MUST use configurable environment variables (`MODEL`, `SMALL_MODEL`, `WORKDIR`, `PC`) matching the conjure pattern, with sensible defaults for the anvil repository.
- **FR-012**: The seed script MUST verify that Paperclip is running (e.g., `curl localhost:3100/api/health`) before attempting any operations, exiting with a clear error if not.
- **FR-013**: Agents MUST be configured with both a primary model and a "cheap" budget model profile (`runtimeConfig.modelProfiles.cheap`) for recovery retries and low-cost tasks, matching the conjure pattern.

### Key Entities

- **Paperclip Company**: Represents the Anvil project within Paperclip. Has a mission, budget, and contains all goals, projects, and agents.
- **Paperclip Goal**: A hierarchical objective under the company mission. Mission-level goals define the product vision; team-level goals break it into workstreams.
- **Paperclip Project**: A grouping of related work under a goal. Maps to anvil's domain areas (e.g., Core Engine, Web UI, Datasets, Infrastructure).
- **Paperclip Agent**: An AI employee with a role, budget, adapter configuration, and standing instructions. Agents work on tickets using the `opencode_local` adapter.
- **Paperclip Issue/Ticket**: A unit of work assigned to an agent, linked to a project and goal. Agents pick up tickets, work them, and report back.
- **Paperclip Workspace**: A git worktree binding the anvil repository so agents can create branches and PRs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The seed script runs successfully end-to-end in under 60 seconds against a running Paperclip instance.
- **SC-002**: After seeding, the Paperclip UI shows a complete Anvil company with goals, projects, agents, and tickets — all discoverable without additional CLI commands.
- **SC-003**: An agent can be enabled (heartbeat turned on), assigned a ticket, and produce useful work (spec, code, or PR) within 15 minutes of seeding.
- **SC-004**: Total Paperclip spend stays within the configured company budget cap at all times, with soft warning at 80% and hard pause at 100%.
- **SC-005**: Re-running the seed script is safe — company creation is skipped, and the operator receives a clear warning about potential duplicates for goals/projects/agents.

## Assumptions

- Paperclip is already installed and running (`npx paperclipai run` at `http://127.0.0.1:3100`), per the conjure setup documented in `learn-paperclip-with-conjure.md`.
- The same Paperclip instance serves both Conjure and Anvil companies (they are separate companies within the same instance).
- OpenRouter API key is configured for OpenCode (`opencode auth login` or `OPENROUTER_API_KEY`), with access to the model strings used (DeepSeek V4 Flash, GPT-4o-mini).
- The anvil repository path on disk is known and set as the agents' `cwd`.
- OpenCode with the `opencode_local` adapter is the agent runtime, matching the established conjure pattern.
- The operator has `npx paperclipai` CLI available and functional.
- Agent budgets follow the conjure default ($75/mo company hard cap) unless explicitly overridden.
- Heartbeats are created disabled — the operator enables agents deliberately, one at a time.
