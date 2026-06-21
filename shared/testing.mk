# Testing targets

test: $(VENV_DIR)/activate ## Run all tests with coverage
	$(PYTHON) -m pytest tests/ -v --cov=anvil --cov-report=term-missing

test-e2e: $(VENV_DIR)/activate ## Run end-to-end tests only
	$(PYTHON) -m pytest tests/e2e/ -v

test-e2e-seed: $(VENV_DIR)/activate ## Train demo model (makes inference tests pass)
	@echo "=== Seeding demo model (tiny, 400 steps) ==="
	$(PYTHON) scripts/seed_demo_model.py
	@echo "=== Demo model seeded ==="

test-e2e-full: test-e2e-seed ## Seed demo model + run full API e2e suite
	$(PYTHON) -m pytest tests/e2e/api/ -v --timeout=300 2>/dev/null || \
	$(PYTHON) -m pytest tests/e2e/api/ -v --override-ini="addopts="

.PHONY: test test-e2e test-e2e-seed test-e2e-full