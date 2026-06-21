---
aliases:
  - SonarCloud MCP Env Passthrough Bug
code-refs:
  - opencode.json
created: '2026-06-21'
related:
  - '[[Decisions/ADR-001-architecture-decisions]]'
session: 2026-06-21-sonarcloud-mcp-fix
source: agent
tags:
  - type/discovery
  - domain/mcp
  - domain/infrastructure
  - status/draft
title: SonarCloud MCP Docker Env Passthrough Fix
type: discovery
updated: '2026-06-21'
---

# SonarCloud MCP Docker Env Passthrough Fix

## The Problem

The `sonarcloud` MCP server in `opencode.json` was configured using Docker's environment variable passthrough syntax (`-e SONARQUBE_ORG` without `=VALUE`). This syntax only passes through variables already set in the shell's environment. Since `SONARQUBE_ORG` and `SONARQUBE_PROJECT_KEY` were not set in the shell when OpenCode spawned the `sh` process, Docker never received them, and the Java MCP server rejected startup with:

```
java.lang.IllegalArgumentException: SONARQUBE_URL or SONARQUBE_ORG must be set.
```

## The Fix

Changed the Docker run command in `opencode.json` from env passthrough to inline values:

```
# Before (broken)
-e SONARQUBE_ORG -e SONARQUBE_PROJECT_KEY

# After (fixed)
-e SONARQUBE_ORG=shapeandshare -e SONARQUBE_PROJECT_KEY=shapeandshare_anvil
```

These values are project constants defined in `shared/sonar.mk` and were already used inline in the `sonar-mcp` Makefile target (which worked). The `opencode.json` config simply hadn't been updated to match.

## Related

- `shared/sonar.mk` — source of truth for `SONAR_ORG` and `SONAR_PROJECT_KEY`
- `opencode.json` — the MCP config that needed fixing
