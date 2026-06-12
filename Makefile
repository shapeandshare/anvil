VENV_DIR := .venv
VENV_BIN := $(VENV_DIR)/bin
PYTHON := $(VENV_BIN)/python3
PYTHON_MAIN := /opt/homebrew/bin/python3.11

# Auto-create venv if missing
$(VENV_DIR)/activate: pyproject.toml
	$(PYTHON_MAIN) -m venv $(VENV_DIR)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .
	@touch $(VENV_DIR)/activate

.PHONY: setup run start stop train test lint format typecheck vault progressive clean install help benchmark

setup: $(VENV_DIR)/activate
	$(PYTHON) -m alembic upgrade head
	@echo "✅ Setup complete"

run: $(VENV_DIR)/activate
	$(PYTHON) -c "from microgpt.cli import serve; serve()"

start: $(VENV_DIR)/activate
	@mkdir -p logs; nohup $(PYTHON) -c "from microgpt.cli import serve; serve()" > logs/server.log 2>&1 & echo "Server starting in background (PID $$!). Use 'make stop' to stop it."

stop:
	$(PYTHON) -c "from microgpt.cli import stop; stop()"

train: $(VENV_DIR)/activate
	$(PYTHON) -c "from microgpt.cli import train; train()"

train-gpu: export USE_GPU=true
train-gpu: train

test: $(VENV_DIR)/activate
	$(PYTHON) -m pytest tests/ -v --cov=microgpt --cov-report=term-missing

test-e2e: $(VENV_DIR)/activate
	$(PYTHON) -m pytest tests/e2e/ -v

lint: $(VENV_DIR)/activate
	$(PYTHON) -m ruff check .
	$(PYTHON) -m black --check .
	$(PYTHON) -m isort --check .
	$(PYTHON) -m pylint microgpt/ --disable=R,C

format: $(VENV_DIR)/activate
	$(PYTHON) -m black .
	$(PYTHON) -m isort .

typecheck: $(VENV_DIR)/activate
	$(PYTHON) -m mypy microgpt/

vault: $(VENV_DIR)/activate
	@echo "Open docs/vault/ in Obsidian for the best experience."
	@open docs/vault/ 2>/dev/null || echo "Run: open docs/vault/"

progressive: $(VENV_DIR)/activate
	@for f in train0.py train1.py train2.py train3.py train4.py train5.py; do \
		if [ -f "$$f" ]; then $(PYTHON) "$$f"; fi; \
	done

install:
	$(PYTHON) -m pip install -e .

clean:
	rm -rf $(VENV_DIR) __pycache__ .pytest_cache .mypy_cache .ruff_cache
	rm -rf build dist *.egg-info

help:
	@echo "microgpt-workbench Makefile"
	@echo "  make setup     - Create venv + install deps + init DB"
	@echo "  make run       - Start web server (foreground, Ctrl+C to stop)"
	@echo "  make start     - Start web server in background (detached)"
	@echo "  make stop      - Stop all background services"
	@echo "  make train     - Run training from CLI"
	@echo "  make test      - Run tests"
	@echo "  make lint      - Run ruff/black/isort/pylint"
	@echo "  make format    - Auto-format code"
	@echo "  make clean     - Remove artifacts"