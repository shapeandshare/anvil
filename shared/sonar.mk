# SonarCloud static analysis tooling
#
# DISABLED 2026-07-19 — temporarily disabled. See ci-workflow.yml for status.
#
# Prerequisites:
#   - sonar-scanner CLI: brew install sonar-scanner
#   - SONAR_TOKEN: Generate at https://sonarcloud.io/account/security
#   - sonar-project.properties at repo root (already in place)
#
# SonarCloud project: shapeandshare/anvil
#   Organization: shapeandshare
#   Project key:  shapeandshare_anvil

SONAR_PROJECT_KEY := shapeandshare_anvil
SONAR_ORG := shapeandshare
SONARCLOUD_API := https://sonarcloud.io/api

#############################################################################
# Prerequisite checks (all DISABLED)
#############################################################################

.PHONY: sonar-check
sonar-check: ## [DISABLED] Verify sonar-scanner CLI is installed
	@echo "SKIPPED — SonarCloud is temporarily disabled. Remove the gate in ci-workflow.yml and uncomment targets in shared/sonar.mk to re-enable."

.PHONY: sonar-check-env
sonar-check-env: ## [DISABLED] Verify SONAR_TOKEN is set
	@echo "SKIPPED — SonarCloud is temporarily disabled. Remove the gate in ci-workflow.yml and uncomment targets in shared/sonar.mk to re-enable."

.PHONY: sonar-check-env-mcp
sonar-check-env-mcp:
	@echo "SKIPPED — SonarCloud is temporarily disabled."

#############################################################################
# Scanner (all DISABLED)
#############################################################################

.PHONY: sonar-scan
sonar-scan: ## [DISABLED] Run SonarCloud static analysis
	@echo "SKIPPED — SonarCloud is temporarily disabled. Remove the gate in ci-workflow.yml and uncomment targets in shared/sonar.mk to re-enable."

.PHONY: sonar-scan-docker
sonar-scan-docker: ## [DISABLED] Run SonarCloud analysis via Docker
	@echo "SKIPPED — SonarCloud is temporarily disabled."

#############################################################################
# API queries (all DISABLED)
#############################################################################

.PHONY: sonar-status
sonar-status: ## [DISABLED] Fetch quality gate status
	@echo "SKIPPED — SonarCloud is temporarily disabled."

.PHONY: sonar-issues
sonar-issues: ## [DISABLED] Fetch open bugs, vulnerabilities, and code smells
	@echo "SKIPPED — SonarCloud is temporarily disabled."

.PHONY: sonar-issues-bugs
sonar-issues-bugs: ## [DISABLED] Fetch open bugs only
	@echo "SKIPPED — SonarCloud is temporarily disabled."

.PHONY: sonar-measures
sonar-measures: ## [DISABLED] Fetch quality metrics
	@echo "SKIPPED — SonarCloud is temporarily disabled."

#############################################################################
# MCP server (DISABLED)
#############################################################################

MCP_SONAR_IMAGE := mcp/sonarqube

.PHONY: sonar-mcp
sonar-mcp: ## [DISABLED] Start SonarCloud MCP server
	@echo "SKIPPED — SonarCloud is temporarily disabled. Re-enable the sonarcloud MCP in opencode.json and uncomment targets in shared/sonar.mk."

.PHONY: sonar-mcp-check
sonar-mcp-check: ## [DISABLED] Verify MCP config in opencode.json
	@echo "SKIPPED — SonarCloud is temporarily disabled. sonarcloud MCP is currently disabled in opencode.json."

#############################################################################
# Comprehensive scan (DISABLED)
#############################################################################

.PHONY: sonar-full
sonar-full: ## [DISABLED] Run tests with coverage + SonarCloud analysis
	@echo "SKIPPED — SonarCloud is temporarily disabled."
