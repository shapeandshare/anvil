# Research: Bootstrap Anvil into Paperclip

**Phase**: 0 — Outline & Research  
**Date**: 2026-07-05  
**Feature**: Bootstrap Anvil into Paperclip (`specs/065-paperclip-bootstrap/spec.md`)

## Research Questions

### RQ-1: What Paperclip CLI commands and payload shapes are needed?

**Decision**: Replicate the exact conjure-seed.sh pattern — `npx paperclipai` CLI with JSON payloads via `--payload-json` flag, `--json` output flag, and `node -e` JSON extraction helper.

**Rationale**: The conjure seed script is a proven, working template (verified against Paperclip v2026.626.0). The CLI commands are identical regardless of project:

| Operation | Command Pattern |
|-----------|----------------|
| Company create | `npx paperclipai company create --payload-json '{"name":"X","mission":"Y"}' --json \| json id` |
| Company update (budget) | `npx paperclipai company update "$CID" --payload-json '{"budgetMonthlyCents":7500}' --json` |
| Goal create | `npx paperclipai goal create -C "$CID" --level company\|team --parent-id "$PID" --title "T" --description "D" --json \| json id` |
| Project create | `npx paperclipai project create -C "$CID" --name "N" --goal-ids "$GID" --description "D" --json \| json id` |
| Agent create | `npx paperclipai agent create -C "$CID" --payload-json '{"name":"...","role":"...","adapterType":"opencode_local",...}' --json \| json id` |
| Issue create | `npx paperclipai issue create -C "$CID" --project-id "$PID" --goal-id "$GID" --assignee-agent-id "$AID" --priority high --title "T" --description "D" --json` |

**Alternatives considered**: 
- Paperclip UI manual setup — rejected: not scriptable, error-prone, cannot be version-controlled.
- Paperclip REST API directly — rejected: more complex, CLI handles auth and error formatting.

### RQ-2: What is the correct agent configuration pattern?

**Decision**: Use `opencode_local` adapter with two model profiles (primary + "cheap" budget lane), cwd set to the anvil repo absolute path, heartbeats disabled by default.

**Rationale**: This exactly matches the conjure agent configuration, which was validated against a running Paperclip instance:

```json
{
  "name": "Agent Name",
  "role": "engineer",
  "title": "Display Title",
  "reportsTo": "$PARENT_ID",
  "capabilities": "Job description text",
  "adapterType": "opencode_local",
  "adapterConfig": { "model": "$MODEL", "cwd": "$WORKDIR" },
  "runtimeConfig": { "modelProfiles": { "cheap": { "enabled": true, "adapterConfig": { "model": "$SMALL_MODEL" } } } },
  "budgetMonthlyCents": 2000
}
```

**Model defaults** (matching conjure):
- `MODEL` = `openrouter/deepseek/deepseek-v4-flash`
- `SMALL_MODEL` = `openrouter/openai/gpt-4o-mini`

**Alternatives considered**: None — this is the exact pattern from conjure.

### RQ-3: How should idempotency work?

**Decision**: Check company existence by name before creating. If company exists, skip creation and print warning. Goals, projects, and agents are NOT idempotent (re-running duplicates them — documented limitation).

**Rationale**: Exact conjure pattern. The idempotency check:
```bash
CID=$($PC company list --json | node -e '...find(x=>x.name==="Anvil")...')
if [ -z "$CID" ]; then
  # create company
else
  echo "company exists: $CID"
fi
```

**Alternatives considered**: 
- Full idempotency (check each entity by name) — rejected: adds significant complexity to a one-time bootstrap script. Conjure chose the simpler approach.

### RQ-4: What agent staffing structure fits anvil?

**Decision**: Three agents mirroring the conjure pattern but adapted for anvil's maturity:

| Agent | Role | Monthly Budget | Capabilities |
|-------|------|---------------|--------------|
| Anvil CEO | ceo | $20 | Strategy, epic prioritization, spec sequencing, delegation to engineers, weekly board updates. Routes work across anvil's domains: core engine, web UI, API, training, datasets, operations. |
| Platform Engineer | engineer | $30 | Core engine (Python, torch, zero-dep libs), training pipeline, API layer (FastAPI), storage, ops (Docker, MLflow, CI/CD). Implements specs via TDD. Works across `anvil/core/`, `anvil/services/training/`, `anvil/api/`. |
| UX Engineer | engineer | $25 | Web UI (Jinja2 templates, CSS design system, FastAPI routes), design system governance (tokens.css, ux-rules.md), accessibility, visual polish. Works across `anvil/api/static/`, `anvil/api/templates/`, `docs/ux-rules.md`. |

**Rationale**: Anvil has 8 distinct work domains. Splitting into Platform (backend/ops) and UX (frontend/design) with a CEO routing hub covers the two major work shapes. The CEO handles the non-engineering work (strategy, specs, prioritization). This is a direct adaptation of conjure's CEO + Engineer + Q/A structure, swapping Q/A for UX since anvil's maturity demands UI polish rather than fidelity review.

**Alternatives considered**:
- Single engineer (conjure pattern) — rejected: anvil has both backend and frontend work streams that benefit from parallel execution.
- 4 agents (CEO + Platform + UX + ML Engineer) — rejected: premature (YAGNI). The ML/v training work is a subset of Platform Engineer's domain until volume justifies specialization.

### RQ-5: What projects and goals should structure the Anvil company?

**Decision**:

**Mission**: "Train and experiment with LLMs from scratch — a pip-installable workbench with live training dashboards, MLflow tracking, and a polished web UI."

**Goals**:
| Level | Title | Description |
|-------|-------|-------------|
| Company (mission) | Anvil v1: reliable LLM workbench from scratch | A user installs anvil, configures a model, picks training data, and watches it learn — all from a polished web UI. Everything traces to this. |
| Team | Core engine & training pipeline is reliable and extensible | The zero-dependency core, torch backend, dataset management, experiment tracking, and model export work correctly and are well-tested. |
| Team | Web UI is polished, responsive, and feature-complete | All 9 web pages (dashboard, datasets, training, experiments, models, playground, learn, operations) are usable, accessible, and visually refined. |

**Projects**:
| Project | Goal | Description |
|---------|------|-------------|
| Core Engine & Training | Core engine goal | The stdlib-only transformer engine, torch training backend, checkpointing, memory estimation, and model export pipeline. |
| Web UI & Design System | Web UI goal | Jinja2 templates, CSS design system (tokens/components/archetypes), FastAPI route integration, UX rules and linting. |
| API & Data Services | Core engine goal | FastAPI REST API, async SQLAlchemy data layer, dataset management, MLflow integration, repository/service/god class layer. |
| Operations & Infrastructure | Core engine goal | Docker deployment, CI/CD pipeline, MLflow sidecar management, backup/restore, SonarCloud quality gates. |

**Rationale**: Four projects covering anvil's architectural layers. Projects 1, 3, and 4 share the core engine goal (quality + reliability); Project 2 gets its own goal (UI polish requires distinct focus).

**Alternatives considered**: 2 projects — rejected: too coarse for useful work assignment. 6 projects — rejected: violates YAGNI.

## Dependency Check

| Dependency | Status | Notes |
|------------|--------|-------|
| Paperclip instance running | ✅ Available at `http://127.0.0.1:3100` | Verified via `~/.paperclip/instances/default/config.json` |
| OpenRouter / OpenCode key | ✅ Assumed configured | `opencode auth login` or `OPENROUTER_API_KEY` required |
| `npx paperclipai` CLI | ✅ Available | Node 20+ required |
| Model strings in OpenCode | ✅ Verified for conjure | DeepSeek V4 Flash + GPT-4o-mini |

## Technology Choices

| Choice | Decision | Rationale |
|--------|----------|-----------|
| Agent adapter | `opencode_local` | Proven with conjure; uses existing OpenCode installation |
| Model (primary) | `openrouter/deepseek/deepseek-v4-flash` | Conjure-proven; fast, cheap |
| Model (budget) | `openrouter/openai/gpt-4o-mini` | Conjure-proven; budget recovery lane |
| CLI tool | `npx paperclipai` | Same as conjure; no install needed |
| GitHub workspace | Bind repo as git workspace | Conjure pattern; agents create branches in worktrees |
| Heartbeat default | Disabled | Operator enables deliberately — safety first |

## Unknowns Resolved

All research questions answered. No NEEDS CLARIFICATION items remain.