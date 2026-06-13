# Database management targets (Alembic migrations)

setup: $(VENV_DIR)/activate ## Create venv, install deps, and run DB migrations
	$(PYTHON) -m alembic upgrade head
	@echo "Setup complete"

db-upgrade: $(VENV_DIR)/activate ## Run all pending Alembic migrations
	$(PYTHON) -m alembic upgrade head

db-downgrade: $(VENV_DIR)/activate ## Rollback last Alembic migration
	$(PYTHON) -m alembic downgrade -1

db-current: $(VENV_DIR)/activate ## Show current Alembic migration revision
	$(PYTHON) -m alembic current

db-history: $(VENV_DIR)/activate ## Show Alembic migration history
	$(PYTHON) -m alembic history

db-revision: $(VENV_DIR)/activate ## Create a new Alembic migration (usage: MESSAGE="description")
	@if [ -z "$(MESSAGE)" ]; then \
		echo "Usage: make db-revision MESSAGE=\"your migration description\""; \
		exit 1; \
	fi
	$(PYTHON) -m alembic revision --autogenerate -m "$(MESSAGE)"
	@echo "Review the generated migration before committing."

db-stamp: $(VENV_DIR)/activate ## Stamp the DB at a specific revision (usage: REVISION=<hash>)
	@if [ -z "$(REVISION)" ]; then \
		echo "Usage: make db-stamp REVISION=<revision-hash>"; \
		exit 1; \
	fi
	$(PYTHON) -m alembic stamp $(REVISION)

.PHONY: setup db-upgrade db-downgrade db-current db-history db-revision db-stamp