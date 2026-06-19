"""Verify the built wheel contains all required resources and metadata.

This is an artifact-inspection test: it opens the .whl with zipfile and
checks dist-info/METADATA. It does NOT import or exercise anvil source,
so it correctly lives under tests/system/ (coverage-excluded).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

DIST_DIR = Path("dist")

pytestmark = [
    pytest.mark.skipif(
        not DIST_DIR.is_dir() or not list(DIST_DIR.glob("anvil-*.whl")),
        reason="No wheel found in dist/ — run 'make build' first",
    ),
]


def _wheel_path() -> Path:
    wheels = sorted(DIST_DIR.glob("anvil-*.whl"))
    assert wheels, f"No anvil-*.whl found in {DIST_DIR.resolve()}"
    return wheels[-1]


def test_wheel_exists() -> None:
    assert _wheel_path().exists()


def test_wheel_produces_single_artifact() -> None:
    wheels = list(DIST_DIR.glob("anvil-*.whl"))
    assert len(wheels) >= 1


def test_wheel_contains_bundled_alembic_ini() -> None:
    import zipfile

    with zipfile.ZipFile(_wheel_path()) as zf:
        names = zf.namelist()
    # .whl contents are under anvil-<version>.data/ or just anvil/
    relevant = [n for n in names if "anvil/_resources/alembic.ini" in n]
    assert relevant, (
        "Wheel missing anvil/_resources/alembic.ini. "
        "Check [tool.setuptools.package-data] in pyproject.toml"
    )


def test_wheel_contains_migration_versions() -> None:
    import zipfile

    with zipfile.ZipFile(_wheel_path()) as zf:
        names = zf.namelist()
    versions = [n for n in names if "anvil/_resources/migrations/versions/" in n and n.endswith(".py")]
    # Expect at least 13 version files (002b + 006 merge = 14 version files + 1 merge = 14+)
    assert len(versions) >= 13, (
        f"Expected at least 13 migration version files in wheel, found {len(versions)}. "
        "Check [tool.setuptools.package-data] for _resources/migrations/versions/*.py"
    )
    # Verify merge head is included
    merge = [v for v in versions if "merge" in v.lower()]
    assert len(merge) >= 1, (
        "No merge revision found in wheel versions. "
        "The 12a4027155f0_merge file must be bundled."
    )


def test_wheel_contains_demo_content() -> None:
    import zipfile

    with zipfile.ZipFile(_wheel_path()) as zf:
        names = zf.namelist()
    demo = [n for n in names if "anvil/data/demo/" in n]
    assert len(demo) >= 3, (
        f"Expected demo content in wheel, found {len(demo)} entries. "
        "Check [tool.setuptools.package-data] for data/demo/**/*.txt"
    )


def test_wheel_contains_static_assets() -> None:
    import zipfile

    with zipfile.ZipFile(_wheel_path()) as zf:
        names = zf.namelist()
    static = [n for n in names if "anvil/api/static/" in n]
    assert len(static) >= 1, (
        "Wheel missing API static assets. Check [tool.setuptools.package-data] for api/static/**/*"
    )


def test_wheel_contains_templates() -> None:
    import zipfile

    with zipfile.ZipFile(_wheel_path()) as zf:
        names = zf.namelist()
    templates = [n for n in names if "anvil/api/templates/" in n]
    assert len(templates) >= 1, (
        "Wheel missing API templates. Check [tool.setuptools.package-data] for api/templates/**/*"
    )


def test_wheel_metadata_lists_requires_python() -> None:
    import zipfile

    with zipfile.ZipFile(_wheel_path()) as zf:
        names = zf.namelist()
        meta = [n for n in names if n.endswith("METADATA") and "dist-info" in n]
        assert meta, "No METADATA file in wheel"
        text = zf.read(meta[0]).decode("utf-8")
    assert "Requires-Python: >=3.11" in text, (
        f"METADATA missing Requires-Python: >=3.11. Got:\n{text[:500]}"
    )


def test_wheel_metadata_lists_base_deps() -> None:
    import zipfile

    with zipfile.ZipFile(_wheel_path()) as zf:
        names = zf.namelist()
        meta = [n for n in names if n.endswith("METADATA") and "dist-info" in n]
        assert meta, "No METADATA file in wheel"
        text = zf.read(meta[0]).decode("utf-8")
    for dep in ("fastapi", "uvicorn", "sqlalchemy", "alembic", "jinja2", "mlflow"):
        assert dep in text, (
            f"METADATA missing base dependency '{dep}'. Got:\n{text[:1000]}"
        )


def test_wheel_metadata_does_not_require_torch() -> None:
    import zipfile

    with zipfile.ZipFile(_wheel_path()) as zf:
        names = zf.namelist()
        meta = [n for n in names if n.endswith("METADATA") and "dist-info" in n]
        assert meta, "No METADATA file in wheel"
        text = zf.read(meta[0]).decode("utf-8")
    # Torch is allowed as a gpu extra dependency, but NOT as a base dependency.
    # "Requires-Dist: torch>=2.0; extra == \"gpu\"" is fine.
    # "Requires-Dist: torch>=2.0" alone would be a problem.
    base_lines = [l for l in text.splitlines() if l.startswith("Requires-Dist: torch") and "; extra" not in l]
    assert not base_lines, (
        f"Torch is listed as a base (non-extra) dependency:\n{base_lines}"
        "It should only be in the [gpu] extra."
    )