# Paperclip CLI Contract (Seed Script Interface)

**Phase**: 1 — Design & Contracts  
**Date**: 2026-07-05  
**Feature**: Bootstrap Anvil into Paperclip

## Overview

The `anvil-seed.sh` script interacts with a running Paperclip instance via the `npx paperclipai` CLI. This document defines the exact CLI contract — commands, payload shapes, output formats, and error handling — that the seed script depends on.

**Source of truth**: Paperclip v2026.626.0 CLI, verified against the conjure-seed.sh implementation.

---

## Common Conventions

```bash
# CLI wrapper (overridable via PC env var)
PC=${PC:-"npx paperclipai"}

# JSON extraction helper
json() { node -e 'let d="";process.stdin.on("data",c=>d+=c).on("end",()=>{const j=JSON.parse(d);const p=process.argv[1].split(".");let v=j;for(const k of p){v=v?.[k]}console.log(v??"")})' "$1"; }

# Required: Paperclip running at http://127.0.0.1:3100
# Required: OpenRouter key configured for OpenCode
```

---

## Command: Company List

**Purpose**: Check if the Anvil company already exists (idempotency gate).

```bash
$PC company list --json
```

**Output**: JSON array of companies (or object with `companies`/`items` key):
```json
[
  { "id": "uuid-here", "name": "Conjure", "mission": "..." },
  { "id": "uuid-here", "name": "Anvil", "mission": "..." }
]
```

**Error handling**: If Paperclip is not running, the CLI exits non-zero. The seed script MUST check exit codes and abort.

**Extraction**: `json()` helper with path `id` or `name` on each entry.

---

## Command: Company Create

**Purpose**: Create the Anvil company.

```bash
$PC company create --payload-json '{
  "name": "Anvil",
  "mission": "Train and experiment with LLMs from scratch — a pip-installable workbench with live training dashboards, MLflow tracking, and a polished web UI."
}' --json
```

**Output**: JSON object with company `id`:
```json
{ "id": "uuid-here", "name": "Anvil", ... }
```

**Error handling**: If company name is already taken, exit non-zero (handled by idempotency check above).

---

## Command: Company Update (Budget)

**Purpose**: Set the company-level hard budget cap.

```bash
$PC company update "$CID" --payload-json '{"budgetMonthlyCents": 7500}' --json
```

**Output**: Updated company JSON.

**Notes**: Budget is in cents. 7500 = $75/mo. This MUST be called after company creation.

---

## Command: Goal Create

**Purpose**: Create hierarchical goals under the company.

```bash
# Mission-level (no parent)
$PC goal create -C "$CID" --level company \
  --title "Anvil v1: reliable LLM workbench from scratch" \
  --description "A user installs anvil, configures a model, picks training data, and watches it learn..." \
  --json

# Team-level (with parent)
$PC goal create -C "$CID" --level team --parent-id "$MISSION_GOAL_ID" \
  --title "Core engine & training pipeline is reliable and extensible" \
  --description "..." \
  --json
```

**Parameters**:
- `-C "$CID"`: Company ID
- `--level`: `company` (mission) or `team` (sub-goal)
- `--parent-id`: Required for team-level, omitted for company-level
- `--title`: Short goal title
- `--description`: Detailed description

**Output**: JSON object with goal `id`.

---

## Command: Project Create

**Purpose**: Create workstream projects linked to goals.

```bash
$PC project create -C "$CID" \
  --name "Core Engine & Training" \
  --goal-ids "$GOAL_ID" \
  --description "The stdlib-only transformer engine, torch training backend..." \
  --json
```

**Parameters**:
- `-C "$CID"`: Company ID
- `--name`: Project name
- `--goal-ids`: Space-separated list of goal IDs
- `--description`: Project description

**Output**: JSON object with project `id`.

---

## Command: Agent Create

**Purpose**: Create AI employees.

```bash
$PC agent create -C "$CID" --payload-json '{
  "name": "Anvil CEO",
  "role": "ceo",
  "title": "Chief Executive",
  "capabilities": "Strategy, prioritization, breaking the mission into specs and tickets, delegating to engineers, weekly board updates.",
  "adapterType": "opencode_local",
  "adapterConfig": {
    "model": "openrouter/deepseek/deepseek-v4-flash",
    "cwd": "/path/to/anvil/repo"
  },
  "runtimeConfig": {
    "modelProfiles": {
      "cheap": {
        "enabled": true,
        "adapterConfig": {
          "model": "openrouter/openai/gpt-4o-mini"
        }
      }
    }
  },
  "budgetMonthlyCents": 2000
}' --json
```

**Parameters** (via `--payload-json`):
- `name`: Display name
- `role`: See Agent Roles table
- `title`: Human-readable title
- `reportsTo`: Parent agent UUID (optional — establishes hierarchy)
- `capabilities`: Free-text job description
- `adapterType`: Must be `"opencode_local"`
- `adapterConfig.model`: Primary model string
- `adapterConfig.cwd`: Absolute path to anvil repository
- `runtimeConfig.modelProfiles.cheap`: Budget lane config (see Model Profiles)
- `budgetMonthlyCents`: Monthly budget ceiling in cents

**Agent Roles**:

| Role | When to Use |
|------|-------------|
| `ceo` | Strategy, routing, board reporting |
| `engineer` | Implementation, code work |
| `qa` | Quality assurance, review |
| `designer` | UI/UX design work |

**Model Profiles**:
- Primary model: Used for all standard agent work (DeepSeek V4 Flash)
- "cheap" profile: Used for recovery retries and low-cost internal tasks (GPT-4o-mini)

**Output**: JSON object with agent `id`.

---

## Command: Issue Create

**Purpose**: Create seed tickets assigned to agents.

```bash
$PC issue create -C "$CID" \
  --project-id "$PROJECT_ID" \
  --goal-id "$GOAL_ID" \
  --assignee-agent-id "$AGENT_ID" \
  --priority high \
  --title "Draft v0 architecture: prompt → app spec → live window" \
  --description "Propose the pipeline..." \
  --json
```

**Parameters**:
- `-C "$CID"`: Company ID
- `--project-id`: Linked project
- `--goal-id`: Linked goal
- `--assignee-agent-id`: Assigned agent
- `--priority`: `high`, `medium`, or `low`
- `--title`: Issue title
- `--description`: Issue description

**Output**: JSON object with `identifier` (e.g., `"ANV-1"`).

---

## Health Check Contract

**Purpose**: Verify Paperclip is running before attempting operations.

```bash
curl -sf http://127.0.0.1:3100/api/health > /dev/null 2>&1 || {
  echo "ERROR: Paperclip not running at http://127.0.0.1:3100"
  echo "Start it with: npx paperclipai run"
  exit 1
}
```

**Expected success response**: `{"status":"ok"}` with exit code 0.

**Expected failure**: Connection refused, curl exits non-zero.

---

## Error Handling Contract

| Condition | Behavior | Exit Code |
|-----------|----------|-----------|
| Paperclip not running | Print error message, suggest `npx paperclipai run` | 1 |
| Company already exists | Print "company exists: $CID", continue | 0 (idempotent) |
| CLI command fails | Script fails fast via `set -euo pipefail` | non-zero |
| Duplicate re-seed | Warn about goal/project/agent duplication | 0 (continuable) |