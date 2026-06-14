# Quickstart: Bootstrap LLM Workbench

**Date**: 2026-06-10  
**Prerequisites**: macOS ARM (Apple Silicon), Python 3.11+, make, git

---

## Install

```bash
git clone <repo-url>
cd anvil
make setup
```

`make setup` will:
1. Create a Python virtual environment (if missing)
2. Install all dependencies from the lock file
3. Run `alembic upgrade head` to initialize the database
4. Verify prerequisites

**No manual `source venv/bin/activate` needed** — all `make` commands handle this automatically.

---

## Train (CLI)

```bash
make train
```

Trains anvil on the names dataset for 1000 steps. Outputs:
```
num docs: 32033
vocab size: 27
num params: 4192
step    1 / 1000 | loss 3.3660
step    2 / 1000 | loss 3.4243
...
step 1000 / 1000 | loss 2.3721

--- inference (20 new names) ---
sample  1: kamon
sample  2: ann
...
```

---

## Train (Web UI)

```bash
make run
```

Opens the workbench at `http://<your-ip>:8080`. Access from any device on your LAN. The web UI provides:

- **Training dashboard** — configure hyperparameters, start runs, watch loss in real-time
- **Experiment tracker** — browse past runs, compare loss curves
- **Dataset manager** — upload custom datasets
- **Operations page** — manage services (web, MLflow), view logs
- **Inference** — generate samples from trained models

---

## Custom Dataset

Upload a `.txt` file (one document per line) via the Dataset Manager page in the web UI. Select it on the Training page before starting a run. The model adapts to the new vocabulary automatically.

```bash
# Or via API
curl -X POST http://<host>:8080/v1/datasets \
  -F "file=@my-data.txt" \
  -F "name=my-dataset"
```

---

## GPU Acceleration

```bash
make train-gpu
```

Auto-detects Metal (macOS ARM) or CUDA (Linux). Falls back to CPU if unavailable.

---

## MLflow Tracking

MLflow runs automatically as a background service when you run `make run`. Access the MLflow native UI from the Operations page in the workbench, or directly at `http://<host>:5000`.

---

## Stop

```bash
make stop
```

Gracefully stops all background services (web server, MLflow, training runs).

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ANVIL_PORT` | `8080` | Web server port |
| `ANVIL_DB_PATH` | `./data/anvil.db` | Database file |
| `ANVIL_LOG_DIR` | `./logs/` | Service log directory |
| `ANVIL_MLFLOW_URI` | `sqlite:///./mlruns/mlflow.db` | MLflow tracking URI |

Copy `.env.example` to `.env` and edit to customize.

---

## Development

```bash
# Install in editable mode
pip install -e .

# Run tests
make test

# Lint
make lint

# Format
make format

# Run progressive training scripts
make progressive

# View vault docs
make vault
```

---

## Project Map

```
anvil/         # Python package (implicit namespace)
├── core/         # Stdlib-only training engine
├── db/           # Database repositories + models
├── services/     # Business logic layer
├── api/          # FastAPI server + routes + templates
├── storage/      # File storage abstraction
└── supervisor/   # Process manager

specs/001-bootstrap-llm-workbench/
├── spec.md       # Feature specification
├── plan.md       # Implementation plan
├── research.md   # Technology research
├── data-model.md # Data model definitions
├── contracts/    # API contracts
└── tasks.md      # Implementation tasks

docs/vault/       # Documentation vault
CONSTITUTION.md   # Project constitution
AGENTS.md         # Agent guidelines
```