# Database management targets (delegated to anvil-db CLI)

setup: $(VENV_DIR)/activate ## Create venv, install deps, and run DB migrations
	mkdir -p data
	$(PYTHON) -m anvil.cli db_main upgrade
	$(PYTHON) -m anvil.cli bootstrap_datasets_main
	@echo "Setup complete"

db-upgrade: $(VENV_DIR)/activate ## Run all pending Alembic migrations
	$(PYTHON) -m anvil.cli db_main upgrade

db-downgrade: $(VENV_DIR)/activate ## Rollback last Alembic migration
	$(PYTHON) -m anvil.cli db_main downgrade

db-current: $(VENV_DIR)/activate ## Show current Alembic migration revision
	$(PYTHON) -m anvil.cli db_main current

db-history: $(VENV_DIR)/activate ## Show Alembic migration history
	$(PYTHON) -m anvil.cli db_main history

db-revision: $(VENV_DIR)/activate ## Create a new Alembic migration (usage: MESSAGE="description")
	@if [ -z "$(MESSAGE)" ]; then \
		echo "Usage: make db-revision MESSAGE=\"your migration description\""; \
		exit 1; \
	fi
	$(PYTHON) -m anvil.cli db_main revision -m "$(MESSAGE)"
	@echo "Review the generated migration before committing."

db-stamp: $(VENV_DIR)/activate ## Stamp the DB at a specific revision (usage: REVISION=<hash>)
	@if [ -z "$(REVISION)" ]; then \
		echo "Usage: make db-stamp REVISION=<revision-hash>"; \
		exit 1; \
	fi
	$(PYTHON) -m anvil.cli db_main stamp $(REVISION)

db-verify: $(VENV_DIR)/activate ## Verify all ORM model tables exist in the database
	$(PYTHON) -m anvil.cli db_main verify

.PHONY: setup db-upgrade db-downgrade db-current db-history db-revision db-stamp db-verify