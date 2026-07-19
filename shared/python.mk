# Generic Python development workflow using uv
# This file contains reusable targets for Python projects using uv + venv

VENV_DIR := .venv
VENV_BIN := $(VENV_DIR)/bin
PYTHON := $(VENV_BIN)/python3

# Auto-create venv via uv if missing
$(VENV_DIR)/activate: pyproject.toml uv.lock
	uv venv $(VENV_DIR)
	uv sync --all-extras
	@touch $(VENV_DIR)/activate

install: $(VENV_DIR)/activate ## Install/update all deps (dev + all extras) from lock file
	uv sync --all-extras

install-gpu: $(VENV_DIR)/activate ## Force install with all extras (GPU + finetune + etc.)
	uv sync --all-extras
	@echo "GPU extras installed. Run 'make train-gpu' or toggle GPU in the web UI."
	@$(PYTHON) -c "import torch; msg = 'no GPU detected, will use CPU'; cu = torch.cuda.is_available(); msg = torch.cuda.get_device_name(0) if cu else msg; msg = 'Apple Silicon (MPS)' if torch.backends.mps.is_available() else msg; print(f'Detected: {msg}')" 2>/dev/null || echo "(torch not yet available in this shell)"

lint: $(VENV_DIR)/activate ## Run ruff, black --check, isort --check, pylint, bandit, semgrep, and project-specific checks
	$(PYTHON) -m ruff check .
	$(PYTHON) -m black --check .
	$(PYTHON) -m isort --check .
	$(PYTHON) -m pylint anvil/ --disable=R,C --exit-zero
	$(MAKE) bandit
	$(MAKE) semgrep
	@echo "Checking for disallowed patterns..."
	@! grep -rn '^@dataclass' anvil/ --include='*.py' | grep -v '# noqa: dataclass' || { echo "ERROR: @dataclass is disallowed — use Pydantic BaseModel instead. See constitution.md"; exit 1; }

bandit: $(VENV_DIR)/activate ## Run bandit security linter on the anvil package
	$(PYTHON) -m bandit -r anvil/ -c pyproject.toml

semgrep: $(VENV_DIR)/activate ## Run semgrep SAST on the anvil package
	$(PYTHON) -m semgrep --config=.semgrep.yml anvil/ --error

gitleaks: ## Run gitleaks secrets scan (requires gitleaks binary: brew install gitleaks)
	@if command -v gitleaks >/dev/null 2>&1; then \
		gitleaks detect --source . --no-git -v; \
	else \
		echo "gitleaks not found. Install: brew install gitleaks"; \
		echo "Or run 'make gitleaks-ci' for CI-only scanning."; \
		exit 0; \
	fi

build: ## Build a PEP 517 wheel via uv (fall back to python -m build)
	uv build --wheel --out-dir dist . 2>/dev/null || python3 -m build --wheel --outdir dist .

format: $(VENV_DIR)/activate ## Auto-format with black and isort
	$(PYTHON) -m black .
	$(PYTHON) -m isort .

typecheck: $(VENV_DIR)/activate ## Run mypy strict type checking
	$(PYTHON) -m mypy anvil/ --no-incremental

.PHONY: install build lint format typecheck clean bandit semgrep gitleaks