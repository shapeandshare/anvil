#!/usr/bin/env bash
# anvil-seed.sh — bootstrap the Anvil company inside a running Paperclip instance.
# Prereqs: Paperclip running at http://127.0.0.1:3100 (npx paperclipai run)
# Usage:   ./anvil-seed.sh          (override: MODEL=… SMALL_MODEL=… WORKDIR=… PC=…)
# RUN ONCE: re-running skips the existing company but will duplicate goals/projects/agents.
# Agents are created with heartbeats DISABLED — enable per agent in the UI when ready.
set -euo pipefail

PC=${PC:-"npx paperclipai"}
# OpenCode model strings (provider/model; for OpenRouter the model id has its own slash).
# Sanity-check both against `opencode models` output before first run.
MODEL=${MODEL:-"openrouter/deepseek/deepseek-v4-flash"}
SMALL_MODEL=${SMALL_MODEL:-"openrouter/openai/gpt-4o-mini"}   # budget lane: recovery retries + low-cost tasks
# Where your agents work.
WORKDIR=${WORKDIR:-"/Users/joshburt/.local/share/opencode/worktree/5354809a525912e5a56a6d4a6e81ccf9f89efdf3/quiet-falcon"}
# Every agent gets: primary model + a "cheap" model profile Paperclip uses for its budget lane.
CHEAP_PROFILE="\"runtimeConfig\": { \"modelProfiles\": { \"cheap\": { \"enabled\": true, \"adapterConfig\": { \"model\": \"$SMALL_MODEL\" } } } }"

json() { node -e 'let d="";process.stdin.on("data",c=>d+=c).on("end",()=>{const j=JSON.parse(d);const p=process.argv[1].split(".");let v=j;for(const k of p){v=v?.[k]}console.log(v??"")})' "$1"; }

echo "── 0. Health check: Paperclip running?"
curl -sf http://127.0.0.1:3100/api/health > /dev/null 2>&1 || {
  echo "ERROR: Paperclip not running at http://127.0.0.1:3100"
  echo "Start it with: npx paperclipai run"
  exit 1
}
echo "Paperclip is running."

echo "── 1. Company"
CID=$($PC company list --json | node -e 'let d="";process.stdin.on("data",c=>d+=c).on("end",()=>{const j=JSON.parse(d);const arr=Array.isArray(j)?j:(j.companies??j.items??[]);const c=arr.find(x=>x.name==="Anvil");console.log(c?c.id:"")})')
if [ -z "$CID" ]; then
  CID=$($PC company create --payload-json '{
    "name": "Anvil",
    "mission": "Train and experiment with LLMs from scratch — a pip-installable workbench with live training dashboards, MLflow tracking, and a polished web UI."
  }' --json | json id)
  echo "created company $CID"
else
  echo "company exists: $CID"
  echo "WARNING: Re-running will duplicate goals, projects, and agents."
fi

echo '── 2. Company budget ($75/mo hard cap)'
$PC company update "$CID" --payload-json '{"budgetMonthlyCents":7500}' --json | json budgetMonthlyCents

echo "── 3. Goals"
G_MISSION=$($PC goal create -C "$CID" --level company --title "Anvil v1: reliable LLM workbench from scratch" \
  --description "A user installs anvil, configures a model, picks training data, and watches it learn — all from a polished web UI. Everything below traces to this." --json | json id)
G_CORE=$($PC goal create -C "$CID" --level team --parent-id "$G_MISSION" --title "Core engine & training pipeline is reliable and extensible" \
  --description "The zero-dependency core, torch backend, dataset management, experiment tracking, and model export work correctly and are well-tested." --json | json id)
G_UI=$($PC goal create -C "$CID" --level team --parent-id "$G_MISSION" --title "Web UI is polished, responsive, and feature-complete" \
  --description "All 9 web pages (dashboard, datasets, training, experiments, models, playground, learn, operations) are usable, accessible, and visually refined." --json | json id)
echo "mission=$G_MISSION core=$G_CORE ui=$G_UI"

echo "── 4. Projects"
P_CORE=$($PC project create -C "$CID" --name "Core Engine & Training" --goal-ids "$G_CORE" \
  --description "The stdlib-only transformer engine, torch training backend, checkpointing, memory estimation, and model export pipeline." --json | json id)
P_UI=$($PC project create -C "$CID" --name "Web UI & Design System" --goal-ids "$G_UI" \
  --description "Jinja2 templates, CSS design system (tokens/components/archetypes), FastAPI route integration, UX rules and linting." --json | json id)
P_API=$($PC project create -C "$CID" --name "API & Data Services" --goal-ids "$G_CORE" \
  --description "FastAPI REST API, async SQLAlchemy data layer, dataset management, MLflow integration, repository/service/god class layer." --json | json id)
P_OPS=$($PC project create -C "$CID" --name "Operations & Infrastructure" --goal-ids "$G_CORE" \
  --description "Docker deployment, CI/CD pipeline, MLflow sidecar management, backup/restore, SonarCloud quality gates." --json | json id)
echo "core=$P_CORE ui=$P_UI api=$P_API ops=$P_OPS"

echo "── 5. Agents (all opencode_local)"
A_CEO=$($PC agent create -C "$CID" --payload-json "{
  \"name\": \"Anvil CEO\",
  \"role\": \"ceo\",
  \"title\": \"Chief Executive\",
  \"capabilities\": \"Strategy, epic prioritization, spec sequencing, delegation to engineers, weekly board updates. Routes work across anvil's domains: core engine, web UI, API, training, datasets, operations.\",
  \"adapterType\": \"opencode_local\",
  \"adapterConfig\": { \"model\": \"$MODEL\", \"cwd\": \"$WORKDIR\" },
  $CHEAP_PROFILE,
  \"budgetMonthlyCents\": 2000
}" --json | json id)
A_ENG=$($PC agent create -C "$CID" --payload-json "{
  \"name\": \"Platform Engineer\",
  \"role\": \"engineer\",
  \"title\": \"Platform Engineer\",
  \"reportsTo\": \"$A_CEO\",
  \"capabilities\": \"Core engine (Python, torch, zero-dep libs), training pipeline, API layer (FastAPI), storage, ops (Docker, MLflow, CI/CD). Implements specs via TDD. Works across anvil/core/, anvil/services/training/, anvil/api/.\",
  \"adapterType\": \"opencode_local\",
  \"adapterConfig\": { \"model\": \"$MODEL\", \"cwd\": \"$WORKDIR\" },
  $CHEAP_PROFILE,
  \"budgetMonthlyCents\": 3000
}" --json | json id)
A_UX=$($PC agent create -C "$CID" --payload-json "{
  \"name\": \"UX Engineer\",
  \"role\": \"engineer\",
  \"title\": \"UX Engineer\",
  \"reportsTo\": \"$A_CEO\",
  \"capabilities\": \"Web UI (Jinja2 templates, CSS design system, FastAPI routes), design system governance (tokens.css, ux-rules.md), accessibility, visual polish. Works across anvil/api/static/, anvil/api/templates/, docs/ux-rules.md.\",
  \"adapterType\": \"opencode_local\",
  \"adapterConfig\": { \"model\": \"$MODEL\", \"cwd\": \"$WORKDIR\" },
  $CHEAP_PROFILE,
  \"budgetMonthlyCents\": 2500
}" --json | json id)
echo "ceo=$A_CEO eng=$A_ENG ux=$A_UX"

echo "── 6. Seed tickets"
$PC issue create -C "$CID" --project-id "$P_CORE" --goal-id "$G_CORE" --assignee-agent-id "$A_ENG" --priority high \
  --title "Review and consolidate spec backlog for core engine" \
  --description "Review all existing specs in specs/ for core-engine-related items. Consolidate, prioritize, and propose the next implementation sequence." --json | json identifier
$PC issue create -C "$CID" --project-id "$P_UI" --goal-id "$G_UI" --assignee-agent-id "$A_UX" --priority high \
  --title "Review and consolidate spec backlog for web UI" \
  --description "Review all existing specs in specs/ for UI-related items. Evaluate UX debt, propose polish priorities, and identify design system gaps." --json | json identifier
$PC issue create -C "$CID" --project-id "$P_API" --goal-id "$G_CORE" --assignee-agent-id "$A_ENG" --priority medium \
  --title "Review and consolidate spec backlog for API & data services" \
  --description "Review all existing specs in specs/ for API/data-layer items. Propose API consistency improvements and identify integration test gaps." --json | json identifier
$PC issue create -C "$CID" --project-id "$P_OPS" --goal-id "$G_CORE" --assignee-agent-id "$A_ENG" --priority low \
  --title "Infrastructure health check and ops gap analysis" \
  --description "Audit the current Docker/CI/CD/MLflow setup. Identify gaps, propose improvements, and document known operational issues." --json | json identifier

echo ""
echo "── Done. Anvil company is ready in Paperclip."
echo "   Open http://127.0.0.1:3100 → Anvil"
echo ""
echo "   Next steps:"
echo "   1. Enable agent heartbeats in the Paperclip UI (Agents → enable)"
echo "   2. Agents will pick up their assigned seed tickets"
echo "   3. Review the staffing plan at docs/STAFFING_PLAN.md"
