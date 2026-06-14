# Server management targets

run: $(VENV_DIR)/activate ## Start web server (foreground, Ctrl+C to stop)
	$(PYTHON) -c "from anvil.cli import serve; serve()"

start: $(VENV_DIR)/activate ## Start web server in background (detached)
	@mkdir -p logs; nohup $(PYTHON) -c "from anvil.cli import serve; serve()" > logs/server.log 2>&1 & echo "Server starting in background (PID $$!). Use 'make stop' to stop it."

stop: ## Stop all background services
	$(PYTHON) -c "from anvil.cli import stop; stop()"

.PHONY: run start stop