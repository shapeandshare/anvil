# Testing targets

test: $(VENV_DIR)/activate ## Run all tests with coverage
	$(PYTHON) -m pytest tests/ -v --cov=anvil --cov-report=term-missing

test-e2e: $(VENV_DIR)/activate ## Run end-to-end tests only
	$(PYTHON) -m pytest tests/e2e/ -v

.PHONY: test test-e2e