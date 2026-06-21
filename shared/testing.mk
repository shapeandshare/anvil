# Testing targets

UNIT_BATCH1 = tests/unit/ci/ tests/unit/core/ tests/unit/db/test_corpus_model.py tests/unit/db/test_migration.py tests/unit/db/test_migration_paths.py tests/unit/services/compute/ tests/unit/services/content/ tests/unit/services/test_chunking.py tests/unit/services/test_corpus_loader.py tests/unit/services/test_demo_bootstrap_paths.py tests/unit/services/test_export.py tests/unit/services/test_inference.py tests/unit/services/test_memory_estimator.py tests/unit/services/test_mlflow_capabilities.py tests/unit/test_cli.py tests/unit/test_config.py tests/unit/test_dataset_curation.py tests/unit/test_local_storage.py tests/unit/test_status_vocabulary.py tests/unit/test_supervisor.py tests/unit/test_supervisor_services.py

UNIT_BATCH2 = tests/unit/db/test_corpus_repository.py tests/unit/db/test_training_config_repository.py tests/unit/services/governance/ tests/unit/services/test_corpora.py tests/unit/services/test_corpus_service.py tests/unit/services/test_mlflow_inputs.py tests/unit/services/test_metrics_collectors.py tests/unit/services/test_system_metrics.py tests/unit/services/test_tracking_service.py tests/unit/services/test_training_phases.py tests/unit/test_dataset_export.py tests/unit/test_dataset_import.py

test: $(VENV_DIR)/activate ## Run all tests with coverage
	$(PYTHON) -m pytest $(UNIT_BATCH1) -v --cov=anvil --cov-report= --cov-branch 2>&1 | tail -1
	$(PYTHON) -m pytest $(UNIT_BATCH2) -v --cov=anvil --cov-report=term-missing --cov-branch --cov-append 2>&1 | tail -1

test-e2e: $(VENV_DIR)/activate ## Run end-to-end tests only
	$(PYTHON) -m pytest tests/e2e/ -v

.PHONY: test test-e2e