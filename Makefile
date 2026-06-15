include shared/helper.mk
include shared/python.mk
include shared/server.mk
include shared/testing.mk
include shared/cli.mk
include shared/database.mk

## Convenience aliases

setup-gpu: install-gpu ## Force GPU setup (auto-detected on Apple Silicon / NVIDIA Linux; use this to override)
	@echo ""
	@echo "GPU setup complete. Start the web app with 'make run' or train with 'make train-gpu'."

run-gpu: export ANVIL_DEVICE=auto
run-gpu: run ## Start web server with GPU auto-detection

train-gpu: export USE_GPU=true
train-gpu: $(VENV_DIR)/activate ## Train with GPU acceleration (also defined in cli.mk)
	$(PYTHON) -c "from anvil.cli import train; train()"

docker: ## Build and run via Docker
	docker build -t anvil .
	docker run -p 8080:8080 -p 5001:5001 anvil

setup-hooks: ## Enable conventional commit enforcement hook
	@echo "Configuring git hooks path to .githooks/..."
	git config core.hooksPath .githooks
	@echo "Done. Hook will validate commit messages follow Conventional Commits format."
	@echo "Types: feat, fix, perf, refactor, chore, docs, ci, test, style, build"
