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
	$(VENV_BIN)/semgrep --config=.semgrep.yml anvil/ --error



ANVIL_VERSION := $(shell grep '^version =' pyproject.toml | sed 's/version = "\(.*\)"/\1/')

build: dist/anvil-$(ANVIL_VERSION)-sbom.cyclonedx.json ## Build PEP 517 wheel + CycloneDX SBOM
	uv build --wheel --out-dir dist . 2>/dev/null || python3 -m build --wheel --outdir dist .

sbom: dist/anvil-$(ANVIL_VERSION)-sbom.cyclonedx.json ## Generate CycloneDX 1.5 SBOM (production deps only)
	@echo "SBOM generated: dist/anvil-$(ANVIL_VERSION)-sbom.cyclonedx.json"

dist/anvil-$(ANVIL_VERSION)-sbom.cyclonedx.json: uv.lock pyproject.toml
	@mkdir -p dist
	uv export --format cyclonedx1.5 --no-dev --frozen > "$@"

sbom-full: dist/anvil-$(ANVIL_VERSION)-sbom.full.cyclonedx.json ## Generate CycloneDX 1.5 SBOM with all extras/dev groups
	@echo "Full SBOM generated: dist/anvil-$(ANVIL_VERSION)-sbom.full.cyclonedx.json"

dist/anvil-$(ANVIL_VERSION)-sbom.full.cyclonedx.json: uv.lock pyproject.toml
	@mkdir -p dist
	uv export --format cyclonedx1.5 --all-extras --frozen > "$@"

format: $(VENV_DIR)/activate ## Auto-format with black and isort
	$(PYTHON) -m black .
	$(PYTHON) -m isort .

typecheck: $(VENV_DIR)/activate ## Run mypy strict type checking
	$(PYTHON) -m mypy anvil/ --no-incremental

.PHONY: install build sbom sbom-full lint format typecheck clean bandit semgrep