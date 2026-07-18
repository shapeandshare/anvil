# Quickstart: Bootstrap Anvil into Paperclip

**Phase**: 1 — Design & Contracts  
**Date**: 2026-07-05  
**Feature**: Bootstrap Anvil into Paperclip

## Prerequisites

1. **Paperclip installed and running**:
   ```bash
   npx paperclipai doctor    # verify setup
   npx paperclipai run       # start server (already running? skip)
   curl localhost:3100/api/health  # should return {"status":"ok"}
   ```

2. **OpenRouter key configured for OpenCode**:
   ```bash
   opencode auth login        # set up OpenRouter
   # Or: export OPENROUTER_API_KEY=sk-or-...
   ```

3. **Model strings verified**:
   ```bash
   opencode models | grep -E "deepseek-v4-flash|gpt-4o-mini"
   ```

4. **Node 20+** (for `npx paperclipai` CLI):
   ```bash
   node --version
   ```

5. **This repository checked out** at the known path.

## Quick Start

### Step 1: Run the seed script

```bash
# From the anvil repo root
bash docs/anvil-seed.sh
```

This creates the complete Anvil company structure in Paperclip:
- Company: **Anvil** with $75/mo hard budget cap
- Mission goal + 2 team goals
- 4 projects (Core Engine, Web UI, API & Data, Operations)
- 3 agents (CEO $20/mo, Platform Engineer $30/mo, UX Engineer $25/mo)
- 4 seed tickets (one per project)

### Step 2: Open Paperclip UI

Navigate to [http://localhost:3100](http://localhost:3100) — you should see the **Anvil** company with all goals, projects, agents, and tickets.

### Step 3: Enable an agent

1. Navigate to **Agents → Anvil CEO** (or Platform Engineer / UX Engineer)
2. Verify adapter shows `opencode_local` with correct repo path and model
3. **Enable heartbeat** in the agent settings
4. The agent will wake, check its inbox, and start on its assigned ticket

### Step 4: Monitor work

- **Agents → [Agent Name] → Runs**: View full transcripts
- **Costs**: Spend breakdown by agent, project, and goal
- **Issues**: Ticket statuses update as agents work

## Customizing the Seed

Override environment variables to customize:

```bash
# Use a different primary model
MODEL="openrouter/anthropic/claude-sonnet-4-20260514" bash docs/anvil-seed.sh

# Use a different budget model
SMALL_MODEL="openrouter/openai/gpt-4o-mini" bash docs/anvil-seed.sh

# Point agents at a different working directory
WORKDIR="/Users/me/Projects/anvil" bash docs/anvil-seed.sh

# Use a different Paperclip CLI path/alias
PC="paperclipai" bash docs/anvil-seed.sh
```

## Safety

- **Heartbeats are disabled by default**. No agent runs until you explicitly enable them.
- **Budget is capped at $75/mo company-wide**. Soft warning at 80%, hard pause at 100%.
- **Re-running is safe** — company creation is idempotent, but goals/projects/agents may duplicate. Run once.
- **Reserved powers** (constitution amendments, version bumps, merges, hiring approvals, budget changes) require human approval.

## Next Steps

After seeding, review the [STAFFING_PLAN.md](../../../docs/STAFFING_PLAN.md) for detailed agent charters, escalation paths, and sequencing.

From there:
1. Enable CEO heartbeat → CEO reviews spec backlog and creates tickets
2. Enable Engineer/UX heartbeats → Engineers pick up tickets
3. Review agent output via Paperclip UI
4. Human merges PRs (reserved power)