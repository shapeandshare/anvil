"""Tests: MigrationService resolves paths from the installed package.

These tests describe the DESIRED behavior after the packaging refactor:
alembic.ini and migrations/ are resolved via importlib.resources, not CWD.
They should fail until T010 is implemented.
"""

from pathlib import Path

import pytest

from anvil.db.migration import MigrationService


def test_migration_service_uses_importlib_resources() -> None:
    """ALEMBIC_INI resolves from inside the anvil package, not the repo root."""
    from anvil.db.migration import ALEMBIC_INI

    ini_path = Path(ALEMBIC_INI)
    assert ini_path.exists(), f"Alembic ini not found at {ini_path}"
    # The ini file must live INSIDE the anvil package directory
    assert "anvil" in ini_path.parts, (
        f"alembic.ini at {ini_path} is outside the anvil package"
        " — was the relocation (T008) completed?"
    )
    assert "anvil" in str(ini_path.resolve()), (
        "alembic.ini path must point inside the anvil package, "
        "not the repo root"
    )


def test_script_location_points_to_packaged_migrations() -> None:
    """The Alembic script_location is overridden to the bundled migrations dir."""
    from anvil.config import get_config

    cfg = get_config()
    db_url = f"sqlite+aiosqlite:///{cfg['state_db_path']}"
    svc = MigrationService(db_url=db_url)

    alembic_cfg = svc._alembic_cfg
    script_location = alembic_cfg.get_main_option("script_location")
    assert script_location is not None
    sl_path = Path(script_location)
    assert sl_path.exists(), f"script_location {script_location} does not exist"
    # Must point inside the anvil package
    assert "anvil" in sl_path.parts, (
        f"script_location {script_location} is outside the anvil package"
    )


def test_migrations_dir_contains_version_files() -> None:
    """The resolved migrations directory contains version files incl. merge head."""
    from anvil.config import get_config

    cfg = get_config()
    db_url = f"sqlite+aiosqlite:///{cfg['state_db_path']}"
    svc = MigrationService(db_url=db_url)

    alembic_cfg = svc._alembic_cfg
    script_location = alembic_cfg.get_main_option("script_location")
    versions_dir = Path(script_location) / "versions"
    assert versions_dir.is_dir(), f"versions dir not found at {versions_dir}"
    py_files = list(versions_dir.glob("*.py"))
    assert len(py_files) >= 1, (  # At least the squashed 001_initial
        f"Expected at least 1 migration version file in {versions_dir}, "
        f"found {len(py_files)}. "
        "Migrate from the relocated package (T009) completed?"
    )
    # Verify the initial revision is present
    initial_files = [f for f in py_files if "001_initial" in f.name]
    assert len(initial_files) >= 1, (
        f"No initial revision found in {versions_dir}. "
        "001_initial.py must be bundled."
    )


@pytest.mark.skip(reason="Requires code change T010 — test documents contract")
def test_migration_service_does_not_use_cwd_alembic_ini() -> None:
    """MigrationService must NOT fall back to a CWD-relative alembic.ini.

    This test would fail currently because the code resolves ALEMBIC_INI
    relative to __file__ in a way that points to the repo root.
    After T010, the path is package-relative.
    """
    from anvil.config import get_config

    cfg = get_config()
    db_url = f"sqlite+aiosqlite:///{cfg['state_db_path']}"
    # Pretend CWD has no alembic.ini
    cwd_pyproject = Path.cwd() / "alembic.ini"
    assert not cwd_pyproject.exists(), (
        "Test precondition failed: alembic.ini in CWD would mask the test."
    )
    svc = MigrationService(db_url=db_url)
    # If this raises FileNotFoundError, the code is still CWD-relative
    svc._build_config("dummy")  # should not look for dummy at CWD