"""anvil — LLM training workbench.

Public API
---------
The ``__version__`` constant is the only public symbol exported by the
package root. All submodules (``anvil.core``, ``anvil.db``,
``anvil.services``, ``anvil.api``, ``anvil.supervisor``) are accessed
via direct import.
"""

import tomllib
from pathlib import Path

# Absolute path to the repository root (parent of the ``anvil/`` package).
_ROOT = Path(__file__).resolve().parent.parent
# Path to the ``pyproject.toml`` file used as the canonical version source.
_PYPROJECT_TOML = _ROOT / "pyproject.toml"

if _PYPROJECT_TOML.exists():
    with open(_PYPROJECT_TOML, "rb") as _f:
        __version__: str = tomllib.load(_f)["project"]["version"]
else:
    from importlib.metadata import version as _metadata_version

    __version__ = _metadata_version("anvil")
