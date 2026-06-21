# SonarCloud static analysis tooling
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

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------

.PHONY: sonar-check
sonar-check: ## Verify sonar-scanner CLI is installed
	@which sonar-scanner >/dev/null 2>&1 || { \
		echo "ERROR: sonar-scanner not found. Install with:"; \
		echo "  brew install sonar-scanner"; \
		echo "  # or:  npm install -g @sonar/scan"; \
		exit 1; \
	}

.PHONY: sonar-check-env
sonar-check-env: ## Verify SONAR_TOKEN is set
	@test -n "$(SONAR_TOKEN)" || { \
		echo "ERROR: SONAR_TOKEN not set."; \
		echo "Generate one at https://sonarcloud.io/account/security"; \
		echo "Then: export SONAR_TOKEN=squ_xxxxx"; \
		exit 1; \
	}

.PHONY: sonar-check-env-mcp
sonar-check-env-mcp:
	@test -n "$(SONARQUBE_TOKEN)" || { \
		echo "ERROR: SONARQUBE_TOKEN not set."; \
		echo "Set: export SONARQUBE_TOKEN=$${SONAR_TOKEN}"; \
		exit 1; \
	}

# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

.PHONY: sonar-scan
sonar-scan: $(VENV_DIR)/activate sonar-check sonar-check-env ## Run SonarCloud static analysis (requires coverage.xml from make test)
	sonar-scanner
	@echo ""
	@echo "SonarCloud analysis submitted."
	@echo "View results at: https://sonarcloud.io/project/overview?id=$(SONAR_PROJECT_KEY)"

.PHONY: sonar-scan-docker
sonar-scan-docker: sonar-check-env ## Run SonarCloud analysis via Docker (no local install needed)
	docker run --rm \
		-e SONAR_TOKEN \
		-e SONAR_HOST_URL="https://sonarcloud.io" \
		-v "$(PWD):/usr/src" \
		sonarsource/sonar-scanner-cli

# ---------------------------------------------------------------------------
# API queries (read-only, requires SONAR_TOKEN)
# ---------------------------------------------------------------------------

.PHONY: sonar-status
sonar-status: sonar-check-env ## Fetch quality gate status
	@curl -s -H "Authorization: Bearer $(SONAR_TOKEN)" \
		"$(SONARCLOUD_API)/qualitygates/project_status?projectKey=$(SONAR_PROJECT_KEY)" | \
		python3 -m json.tool

.PHONY: sonar-issues
sonar-issues: sonar-check-env ## Fetch open bugs, vulnerabilities, and code smells
	@curl -s -H "Authorization: Bearer $(SONAR_TOKEN)" \
		"$(SONARCLOUD_API)/issues/search?componentKeys=$(SONAR_PROJECT_KEY)&types=BUG,VULNERABILITY,CODE_SMELL&statuses=OPEN,CONFIRMED&ps=50" | \
		python3 -m json.tool

.PHONY: sonar-issues-bugs
sonar-issues-bugs: sonar-check-env ## Fetch open bugs only
	@curl -s -H "Authorization: Bearer $(SONAR_TOKEN)" \
		"$(SONARCLOUD_API)/issues/search?componentKeys=$(SONAR_PROJECT_KEY)&types=BUG&statuses=OPEN,CONFIRMED" | \
		python3 -m json.tool

.PHONY: sonar-measures
sonar-measures: sonar-check-env ## Fetch quality metrics (loc, bugs, coverage, duplications, etc.)
	@curl -s -H "Authorization: Bearer $(SONAR_TOKEN)" \
		"$(SONARCLOUD_API)/measures/component?component=$(SONAR_PROJECT_KEY)&metricKeys=ncloc,bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density,security_hotspots,reliability_rating,security_rating,sqale_rating" | \
		python3 -m json.tool

# ---------------------------------------------------------------------------
# MCP server (local Docker for OpenCode / Claude / Cursor integration)
# ---------------------------------------------------------------------------

MCP_SONAR_IMAGE := mcp/sonarqube

.PHONY: sonar-mcp
sonar-mcp: sonar-check-env-mcp ## Start SonarCloud MCP server (Docker, foreground, Ctrl+C to stop)
	docker run --init --pull=always -i --rm \
		-e SONARQUBE_TOKEN \
		-e SONARQUBE_ORG=$(SONAR_ORG) \
		-e SONARQUBE_PROJECT_KEY=$(SONAR_PROJECT_KEY) \
		$(MCP_SONAR_IMAGE)

.PHONY: sonar-mcp-check
sonar-mcp-check: ## Verify MCP config in opencode.json
	@test -f opencode.json || { echo "ERROR: opencode.json not found"; exit 1; }
	@python3 -c "import json; cfg=json.load(open('opencode.json')); mcp=cfg.get('mcp',{}); enabled='sonarcloud' in mcp and mcp['sonarcloud'].get('enabled'); print('OK: sonarcloud MCP is enabled in opencode.json' if enabled else 'WARNING: sonarcloud MCP not found or disabled in opencode.json')"

# ---------------------------------------------------------------------------
# Comprehensive scan: test (with coverage) + sonar analysis
# ---------------------------------------------------------------------------

.PHONY: sonar-full
sonar-full: test sonar-scan ## Run tests with coverage, then run SonarCloud analysis
	@echo "Full SonarCloud scan complete."
