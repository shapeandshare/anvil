"""Tests for CLI entry points with early MLflow patching.

MLflow hangs at import time (network calls). We patch it before
importing any anvil.cli functions.
"""

from __future__ import annotations

import atexit
import sys
import unittest.mock

# Patch mlflow BEFORE any anvil imports to prevent import-time hangs
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

# Save original mlflow modules so they can be restored after tests
_saved_mlflow_modules: dict[str, object] = {}
for _mod_name in (
    "mlflow",
    "mlflow.tracking",
    "mlflow.entities",
    "mlflow.exceptions",
    "mlflow.genai",
    "mlflow.genai.datasets",
    "mlflow.pyfunc",
):
    if _mod_name in sys.modules:
        _saved_mlflow_modules[_mod_name] = sys.modules[_mod_name]

# Build a realistic mlflow mock module tree
_mlflow = ModuleType("mlflow")
_mlflow.tracking = ModuleType("mlflow.tracking")
_mlflow.tracking.MlflowClient = unittest.mock.MagicMock()
_mlflow.tracking.MlflowClient.__module__ = "mlflow.tracking"
_mlflow.MlflowClient = _mlflow.tracking.MlflowClient
_mlflow.tracking.__dict__["MlflowClient"] = _mlflow.tracking.MlflowClient
_mlflow.entities = ModuleType("mlflow.entities")
_mlflow.exceptions = ModuleType("mlflow.exceptions")
_mlflow.exceptions.MlflowException = Exception
_mlflow.genai = ModuleType("mlflow.genai")
_mlflow.genai.datasets = ModuleType("mlflow.genai.datasets")
_mlflow.genai.datasets.create_dataset = None
_mlflow.genai.datasets.get_dataset = None
sys.modules["mlflow"] = _mlflow
sys.modules["mlflow.tracking"] = _mlflow.tracking
sys.modules["mlflow.entities"] = _mlflow.entities
sys.modules["mlflow.exceptions"] = _mlflow.exceptions
sys.modules["mlflow.genai"] = _mlflow.genai
sys.modules["mlflow.genai.datasets"] = _mlflow.genai.datasets
# Provide mlflow.pyfunc so other test modules (e.g. test_pyfunc_model) can import it
_mlflow.pyfunc = type(sys)("mlflow.pyfunc")
_mlflow.pyfunc.PythonModel = type("PythonModel", (), {})
_mlflow.pyfunc.PythonModelContext = type("PythonModelContext", (), {})
sys.modules["mlflow.pyfunc"] = _mlflow.pyfunc


def _restore_mlflow() -> None:
    """Restore original mlflow modules after tests complete."""
    for _mod_name, _mod_value in _saved_mlflow_modules.items():
        if _mod_value is None:
            sys.modules.pop(_mod_name, None)
        else:
            sys.modules[_mod_name] = _mod_value


atexit.register(_restore_mlflow)

import pytest

from anvil.cli import db_main


@pytest.fixture
def mock_migration():
    with patch("anvil.cli.MigrationService") as m:
        inst = MagicMock()
        inst.upgrade = AsyncMock(return_value=(None, "abc"))
        inst.downgrade = AsyncMock(return_value="def")
        inst.current = AsyncMock(return_value=None)
        inst.history = AsyncMock(return_value=["rev1"])
        inst.create_revision = AsyncMock(return_value="new_rev")
        inst.stamp = AsyncMock()
        inst.verify_schema = AsyncMock()
        m.verify_table_integrity = AsyncMock(return_value=["missing_tables"])
        m.return_value = inst
        yield m


class TestDbMainUpgrade:
    def test_upgrade(self, mock_migration):
        db_main(["upgrade"])
        mock_migration.return_value.upgrade.assert_called_once()


class TestDbMainDowngrade:
    def test_downgrade(self, mock_migration):
        db_main(["downgrade", "base"])
        mock_migration.return_value.downgrade.assert_called_once()


class TestDbMainCurrent:
    def test_current(self, mock_migration):
        db_main(["current"])


class TestDbMainHistory:
    def test_history(self, mock_migration):
        entries = [
            {"down_revision": None, "revision": "abc", "message": "first"},
        ]
        mock_migration.return_value.history.return_value = entries
        mock_migration.return_value.current.return_value = "abc"
        db_main(["history"])
        mock_migration.return_value.history.assert_called_once()


class TestDbMainCreateRevision:
    def test_create(self, mock_migration):
        db_main(["revision", "-m", "test migration"])
        mock_migration.return_value.create_revision.assert_called_once()


class TestDbMainStamp:
    def test_stamp(self, mock_migration):
        db_main(["stamp", "abc123"])
        mock_migration.return_value.stamp.assert_called_once()


class TestDbMainVerify:
    def test_verify(self, mock_migration):
        with pytest.raises(SystemExit) as exc:
            db_main(["verify"])
        assert exc.value.code == 1
