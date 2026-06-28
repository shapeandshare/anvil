"""Tests for layer boundary checker."""

from __future__ import annotations

from anvil.services.vault.check_layer_boundaries import _check_imports, _classify_file


class TestClassifyFile:
    """Tests for ``_classify_file``."""

    def test_routes_layer(self) -> None:
        layer = _classify_file("anvil/api/v1/routes.py")
        assert layer == "routes"

    def test_repositories_layer(self) -> None:
        layer = _classify_file("anvil/db/repositories/training_repo.py")
        assert layer == "repositories"

    def test_models_layer(self) -> None:
        layer = _classify_file("anvil/db/models/training_run.py")
        assert layer == "models"

    def test_services_layer(self) -> None:
        layer = _classify_file("anvil/services/training/orchestrator.py")
        assert layer == "services"

    def test_core_layer(self) -> None:
        layer = _classify_file("anvil/core/engine.py")
        assert layer == "core"

    def test_unknown_layer(self) -> None:
        layer = _classify_file("anvil/storage/file_store.py")
        assert layer is None

    def test_supervisor_unknown(self) -> None:
        layer = _classify_file("anvil/supervisor/manager.py")
        assert layer is None

    def test_prefix_order_matters(self) -> None:
        layer = _classify_file("anvil/db/repositories/repo.py")
        assert layer == "repositories"


class TestCheckImports:
    """Tests for ``_check_imports``."""

    ROUTE_PATH = "anvil/api/v1/routes.py"
    SERVICE_PATH = "anvil/services/training/run.py"
    REPO_PATH = "anvil/db/repositories/repo.py"
    CORE_PATH = "anvil/core/engine.py"
    MODEL_PATH = "anvil/db/models/run.py"

    def test_routes_not_import_repositories(self) -> None:
        source = "from anvil.db.repositories import TrainingRepository\n"
        issues = _check_imports(source, self.ROUTE_PATH, "routes")
        assert len(issues) == 1
        assert issues[0].target == "anvil.db.repositories"
        assert issues[0].layer == "routes"
        assert issues[0].line == 1

    def test_routes_not_import_services_directly(self) -> None:
        source = "from anvil.services.training import run_training\n"
        issues = _check_imports(source, self.ROUTE_PATH, "routes")
        assert len(issues) == 1
        assert issues[0].target == "anvil.services"
        assert issues[0].layer == "routes"

    def test_routes_not_import_models(self) -> None:
        source = "import anvil.db.models\n"
        issues = _check_imports(source, self.ROUTE_PATH, "routes")
        assert len(issues) == 1
        assert issues[0].target == "anvil.db.models"

    def test_routes_import_std_lib_allowed(self) -> None:
        source = "import os\nimport re\nfrom dataclasses import dataclass\n"
        issues = _check_imports(source, self.ROUTE_PATH, "routes")
        assert issues == []

    def test_services_not_import_api(self) -> None:
        source = "from anvil.api import app\n"
        issues = _check_imports(source, self.SERVICE_PATH, "services")
        assert len(issues) == 1
        assert issues[0].target == "anvil.api"
        assert issues[0].layer == "services"

    def test_services_can_import_repositories(self) -> None:
        source = "from anvil.db.repositories import TrainingRepository\n"
        issues = _check_imports(source, self.SERVICE_PATH, "services")
        assert issues == []

    def test_repositories_not_import_services(self) -> None:
        source = "from anvil.services.training import run_training\n"
        issues = _check_imports(source, self.REPO_PATH, "repositories")
        assert len(issues) == 1
        assert issues[0].target == "anvil.services"

    def test_repositories_not_import_api(self) -> None:
        source = "import anvil.api\n"
        issues = _check_imports(source, self.REPO_PATH, "repositories")
        assert len(issues) == 1
        assert issues[0].target == "anvil.api"

    def test_core_not_import_anvil(self) -> None:
        source = "import anvil.db\n"
        issues = _check_imports(source, self.CORE_PATH, "core")
        assert len(issues) == 1
        assert issues[0].target == "anvil."

    def test_core_import_stdlib_allowed(self) -> None:
        source = "import math\nfrom pathlib import Path\n"
        issues = _check_imports(source, self.CORE_PATH, "core")
        assert issues == []

    def test_models_not_import_services(self) -> None:
        source = "from anvil.services.training import TrainingRun\n"
        issues = _check_imports(source, self.MODEL_PATH, "models")
        assert len(issues) == 1
        assert issues[0].target == "anvil.services"

    def test_models_not_import_api(self) -> None:
        source = "from anvil.api.v1 import routes\n"
        issues = _check_imports(source, self.MODEL_PATH, "models")
        assert len(issues) == 1
        assert issues[0].target == "anvil.api"

    def test_models_not_import_repositories(self) -> None:
        source = "import anvil.db.repositories\n"
        issues = _check_imports(source, self.MODEL_PATH, "models")
        assert len(issues) == 1
        assert issues[0].target == "anvil.db.repositories"

    def test_no_violation_clean(self) -> None:
        source = (
            "from __future__ import annotations\n"
            "import os\n"
            "from pathlib import Path\n\n"
            "LOWERCASE = False\n"
        )
        issues = _check_imports(source, self.ROUTE_PATH, "routes")
        assert issues == []

    def test_unknown_layer_skipped(self) -> None:
        source = "import anvil.api\n"
        issues = _check_imports(source, "anvil/storage/store.py", None)
        assert issues == []

    def test_multiple_violations_in_one_file(self) -> None:
        source = (
            "import os\n"
            "from anvil.db.repositories import Repo\n"
            "import anvil.services.training\n"
        )
        issues = _check_imports(source, self.ROUTE_PATH, "routes")
        assert len(issues) == 2
        targets = {i.target for i in issues}
        assert targets == {"anvil.db.repositories", "anvil.services"}

    def test_violation_line_numbers(self) -> None:
        source = (
            "import os\n" "import sys\n" "from anvil.services.training import run\n"
        )
        issues = _check_imports(source, self.ROUTE_PATH, "routes")
        assert len(issues) == 1
        assert issues[0].line == 3

    def test_comment_line_not_a_violation(self) -> None:
        source = "# from anvil.services import training\n"
        issues = _check_imports(source, self.ROUTE_PATH, "routes")
        assert issues == []

    def test_from_import_detected(self) -> None:
        source = "from anvil.db.repositories import X\n"
        issues = _check_imports(source, self.ROUTE_PATH, "routes")
        assert len(issues) == 1

    def test_import_statement_detected(self) -> None:
        source = "import anvil.db.repositories\n"
        issues = _check_imports(source, self.ROUTE_PATH, "routes")
        assert len(issues) == 1
