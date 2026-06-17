"""anvil — LLM training workbench."""

import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PYPROJECT_TOML = _ROOT / "pyproject.toml"

if _PYPROJECT_TOML.exists():
    with open(_PYPROJECT_TOML, "rb") as _f:
        __version__: str = tomllib.load(_f)["project"]["version"]
else:
    from importlib.metadata import version as _metadata_version

    __version__ = _metadata_version("anvil")
