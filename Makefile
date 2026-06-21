include shared/helper.mk
include shared/python.mk
include shared/server.mk
include shared/testing.mk
include shared/cli.mk
include shared/database.mk
include shared/vault.mk
include shared/sonar.mk

## Convenience aliases

setup-gpu: install-gpu ## Force GPU setup (auto-detected on Apple Silicon / NVIDIA Linux; use this to override)
	@echo ""
	@echo "GPU setup complete. Start the web app with 'make run' or train with 'make train-gpu'."

run-gpu: export ANVIL_DEVICE=auto
run-gpu: run ## Start web server with GPU auto-detection

train-gpu: $(VENV_DIR)/activate ## Train with GPU acceleration (--backend local-gpu)
	$(PYTHON) -c "import sys; sys.argv += ['--backend', 'local-gpu']; from anvil.cli import train; train()"

docker: ## [deprecated] Use `make compose-up` instead (multi-stage pip-installed build)
	@echo "DEPRECATED: Use 'make compose-up' which builds + runs via compose.yaml."
	@echo "See specs/009-pip-installable-package/quickstart.md for the validation loop."

compose-up: ## Build image from wheel, bring online via compose, wait for health
	docker compose up -d --build --wait

compose-down: ## Tear down the stack (retains workspace volume)
	docker compose down

compose-reset: ## Tear down and remove the workspace volume (fresh first-run next)
	docker compose down -v

test-system: ## Full validation loop: reset → up → test → teardown
	docker compose down -v; \
	docker compose up -d --build --wait; \
	uv run pytest tests/system -v --no-cov; status=$$?; \
	docker compose down -v; \
	exit $$status

test-browser: ## Browser smoke loop: reset → up → playwright tests → teardown
	docker compose down -v; \
	docker compose up -d --build --wait; \
	uv run pytest tests/browser -v --no-cov; status=$$?; \
	docker compose down -v; \
	exit $$status

setup-hooks: ## Enable conventional commit enforcement hook
	@echo "Configuring git hooks path to .githooks/..."
	git config core.hooksPath .githooks
	@echo "Done. Hook will validate commit messages follow Conventional Commits format."
	@echo "Types: feat, fix, perf, refactor, chore, docs, ci, test, style, build"

clean: ## Wipe all runtime state and build artifacts for a fresh start
	rm -f data/anvil-state.db mlruns/mlflow.db
	rm -rf dist/ .coverage htmlcov .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned. Run 'make run' to rebuild from scratch."
