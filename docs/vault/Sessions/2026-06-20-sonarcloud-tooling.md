---
created: '2026-06-20'
status: draft
source: agent
tags:
  - domain/tooling
  - domain/infrastructure
  - type/session-log
title: SonarCloud Tooling Integration — 2026-06-20
type: session-log
updated: '2026-06-20'
aliases:
  - SonarCloud Tooling Integration
---
# SonarCloud Tooling Integration

**Date**: 2026-06-20
**Context**: User asked to wire SonarCloud static analysis into the local developer toolchain (Makefile, CI, MCP server) alongside the existing ruff/black/isort/pylint/mypy quality gates.

## What Was Done

### New Shared Makefile: `shared/sonar.mk`

Created a standalone makefile for all SonarCloud interaction, following the project's modular pattern (`shared/*.mk` is included by the root `Makefile`). 11 targets:

| Target | Purpose |
|--------|---------|
| `sonar-check` | Verify `sonar-scanner` CLI is installed (brew) |
| `sonar-check-env` | Verify `SONAR_TOKEN` is set |
| `sonar-scan` | Run `sonar-scanner` with coverage data |
| `sonar-scan-docker` | Run via Docker (`sonarsource/sonar-scanner-cli`) without local install |
| `sonar-status` | Fetch quality gate status from SonarCloud API |
| `sonar-issues` | Fetch open bugs/vulnerabilities/code smells |
| `sonar-issues-bugs` | Fetch open bugs only |
| `sonar-measures` | Fetch quality metrics (ncloc, coverage, duplications, ratings) |
| `sonar-mcp` | Start the official SonarSource MCP server (`mcp/sonarqube`) via Docker |
| `sonar-mcp-check` | Verify the MCP config entry in `opencode.json` |
| `sonar-full` | Composite: `make test` + `make sonar-scan` (one-shot) |

### New Files

- **`sonar-project.properties`** — Project-level config for the SonarCloud scanner: organization `shapeandshare`, project key `shapeandshare_anvil`, sources `anvil/`, exclusions `anvil/_resources/**`.
- **`shared/sonar.mk`** — Make targets (see above).

### Modified Files

- **`Makefile`** — Added `include shared/sonar.mk` on line 8.
- **`.github/workflows/ci.yml`** — Added `sonar-scan` CI gate job using the official `SonarSource/sonarcloud-github-action@master` action. Runs tests (coverage) first, then submits to SonarCloud. Listed in `gate-status` summarizer alongside lint/typecheck/test/vault-audit.
- **`opencode.json`** — Added `sonarcloud` MCP server entry running the official `mcp/sonarqube` Docker image with env vars `SONARQUBE_TOKEN`, `SONARQUBE_ORG`, `SONARQUBE_PROJECT_KEY`.
- **`AGENTS.md`** — Updated Quick Reference Commands table with all sonar targets, bumped `Last updated` to `sonarcloud-tooling`.

### MCP Integration

The official SonarSource/sonarqube-mcp-server is configured in `opencode.json` as a Docker-based MCP server. It enables OpenCode agents to query issues, quality gates, measures, security hotspots, and more via the standard Model Context Protocol.

## Key Decisions

1. **Separate makefile, not inline**: SonarCloud targets live in `shared/sonar.mk` following the existing modular pattern (vault.mk, database.mk, etc.).
2. **Separate CI job, not merged into lint**: SonarCloud analysis takes longer and has different failure semantics (API upload vs local lint). It runs as a parallel CI gate job.
3. **Dual local/Docker scanner**: `sonar-scan` uses the native CLI (brew), `sonar-scan-docker` uses the Docker image — covers both local-first and CI environments.
4. **Official SonarSource MCP server**: Chose the Docker-based official server over the Python `mcp-sonarcloud` alternative since it has broader tool coverage and active maintenance.

## Related

- [[Reference/linting-and-testing-tooling|Linting, Formatting, and Testing Tooling]] — CI tooling reference
- [[Decisions/ADR-028-ci-merge-gate-enforcement|ADR-028: CI Merge Gate Enforcement]] — related architecture decision
- [[Systems/Systems|Systems]] — tooling and infrastructure systems
