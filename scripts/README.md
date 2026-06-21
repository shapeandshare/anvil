# Scripts

Organized by purpose into three subdirectories:

| Directory | Purpose |
|-----------|---------|
| `dev/` | Developer machine utilities (local environment) |
| `ci/` | CI pipeline building blocks (GitHub Actions) |
| `release/` | Release pipeline helpers (GitHub Actions) |

## Conventions

- **Python preferred over bash** — see AGENTS.md Principle 12 for the full
  rationale.
- **Thin wrappers only** — scripts in ``scripts/`` delegate to ``anvil-vault``
  via ``subprocess``. Business logic lives in importable package modules under
  ``anvil/services/vault/`` and ``anvil/services/_shared/``.
- Shell scripts (``.sh``) are reserved for situations where the Python runtime
  is not guaranteed — e.g., Makefile helpers that run during ``make setup``
  before the venv exists (``dev/detect-gpu-platform.sh``).
- Python scripts use snake_case filenames, the ``if __name__ == "__main__":``
  pattern, and stdlib-only dependencies (no pip installs required at CI time).
- All scripts are designed to be called from GitHub Actions workflow steps or
  Makefile targets. They accept inputs via environment variables and arguments,
  and produce ``key=value`` stdout lines for ``$GITHUB_OUTPUT`` where appropriate.

## Reference

| Script | Called from | Purpose |
|--------|-------------|---------|
| `dev/detect-gpu-platform.sh` | `shared/python.mk` | Detects Apple Silicon / NVIDIA GPU for conditional dep install |
| `ci/detect_increment.py` | `.github/workflows/release.yml` | Classifies merge commit → MAJOR/MINOR/PATCH/SKIP/NONE |
| `ci/check_version.py` | `.github/workflows/auto-bump.yml` | Detects whether version changed since parent commit |
| `release/build_notes.py` | `.github/workflows/release.yml` | Assembles release-notes.md from CHANGELOG + PR body |
