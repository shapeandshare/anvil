# Generic Python development workflow with venv
# This file contains reusable targets for Python projects using venv + pip

VENV_DIR := .venv
VENV_BIN := $(VENV_DIR)/bin
PYTHON := $(VENV_BIN)/python3
PYTHON_MAIN := /opt/homebrew/bin/python3.11

# Auto-detect GPU platform: outputs ",gpu" on Apple Silicon or NVIDIA Linux,
# empty string otherwise. Used to conditionally include GPU extras.
GPU_EXTRA := $(shell ./scripts/detect-gpu-platform.sh)

# Auto-create venv if missing
$(VENV_DIR)/activate: pyproject.toml
	$(PYTHON_MAIN) -m venv $(VENV_DIR)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev$(GPU_EXTRA)]"
	@touch $(VENV_DIR)/activate

install: $(VENV_DIR)/activate ## Install the package in editable mode
	$(PYTHON) -m pip install -e ".[dev$(GPU_EXTRA)]"

install-gpu: $(VENV_DIR)/activate ## Force install with GPU support (torch + CUDA/MPS)
	$(PYTHON) -m pip install -e ".[dev,gpu]"
	@echo "GPU extras installed. Run 'make train-gpu' or toggle GPU in the web UI."
	@$(PYTHON) -c "import torch; msg = 'no GPU detected, will use CPU'; cu = torch.cuda.is_available(); msg = torch.cuda.get_device_name(0) if cu else msg; msg = 'Apple Silicon (MPS)' if torch.backends.mps.is_available() else msg; print(f'Detected: {msg}')" 2>/dev/null || echo "(torch not yet available in this shell)"

lint: $(VENV_DIR)/activate ## Run ruff, black --check, isort --check, pylint
	$(PYTHON) -m ruff check .
	$(PYTHON) -m black --check .
	$(PYTHON) -m isort --check .
	$(PYTHON) -m pylint microgpt/ --disable=R,C

format: $(VENV_DIR)/activate ## Auto-format code with black + isort
	$(PYTHON) -m black .
	$(PYTHON) -m isort .

typecheck: $(VENV_DIR)/activate ## Run mypy type checking
	$(PYTHON) -m mypy microgpt/

clean: ## Remove artifacts and caches
	rm -rf $(VENV_DIR) __pycache__ .pytest_cache .mypy_cache .ruff_cache
	rm -rf build dist *.egg-info
	@echo "Cleaned up."

.PHONY: install lint format typecheck clean