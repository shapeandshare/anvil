# Database management targets (delegated to anvil-db CLI)

setup: $(VENV_DIR)/activate ## Create venv, install deps, and run DB migrations
	mkdir -p data
	$(VENV_BIN)/anvil-db upgrade
	$(PYTHON) -m anvil.cli bootstrap_datasets_main
	@echo "Setup complete"

db-upgrade: $(VENV_DIR)/activate ## Run all pending Alembic migrations
	$(VENV_BIN)/anvil-db upgrade

db-downgrade: $(VENV_DIR)/activate ## Rollback last Alembic migration
	$(VENV_BIN)/anvil-db downgrade

db-current: $(VENV_DIR)/activate ## Show current Alembic migration revision
	$(VENV_BIN)/anvil-db current

db-history: $(VENV_DIR)/activate ## Show Alembic migration history
	$(VENV_BIN)/anvil-db history

db-revision: $(VENV_DIR)/activate ## Create a new Alembic migration (usage: MESSAGE="description")
	@if [ -z "$(MESSAGE)" ]; then \
		echo "Usage: make db-revision MESSAGE=\"your migration description\""; \
		exit 1; \
	fi
	$(VENV_BIN)/anvil-db revision -m "$(MESSAGE)"
	@echo "Review the generated migration before committing."

db-stamp: $(VENV_DIR)/activate ## Stamp the DB at a specific revision (usage: REVISION=<hash>)
	@if [ -z "$(REVISION)" ]; then \
		echo "Usage: make db-stamp REVISION=<revision-hash>"; \
		exit 1; \
	fi
	$(VENV_BIN)/anvil-db stamp $(REVISION)

db-verify: $(VENV_DIR)/activate ## Verify all ORM model tables exist in the database
	$(VENV_BIN)/anvil-db verify

.PHONY: setup db-upgrade db-downgrade db-current db-history db-revision db-stamp db-verify