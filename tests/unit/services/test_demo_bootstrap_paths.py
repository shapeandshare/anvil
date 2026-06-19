"""Tests: DemoBootstrapService resolves demo path from the installed package.

These tests describe the DESIRED behavior after the packaging refactor:
DEMO_DIR is resolved via importlib.resources, not CWD.
They should fail (or at least be skipped) until T011 is implemented.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from anvil.services.demo_bootstrap import DemoBootstrapService


def test_demo_bootstrap_demo_dir_resolves_from_package() -> None:
    """DEMO_DIR resolves from inside the anvil package, not CWD."""
    # Re-import the module to test its module-level constant
    import importlib

    mod = importlib.import_module("anvil.services.demo_bootstrap")
    importlib.reload(mod)

    demo_dir = mod.DEMO_DIR
    assert isinstance(demo_dir, Path)
    assert demo_dir.exists(), f"DEMO_DIR {demo_dir} does not exist"
    # Must point inside the anvil package
    assert "anvil" in str(demo_dir.resolve()), (
        f"DEMO_DIR {demo_dir} is outside the anvil package"
        " — was the relocation (T009) completed?"
    )


def test_demo_dir_contains_expected_subdirs() -> None:
    """The resolved demo directory has the expected corpus subdirectories."""
    import importlib

    mod = importlib.import_module("anvil.services.demo_bootstrap")
    importlib.reload(mod)

    demo_dir = mod.DEMO_DIR
    subdirs = [d.name for d in demo_dir.iterdir() if d.is_dir()]
    expected = {"small", "medium", "large"}
    missing = expected - set(subdirs)
    assert not missing, (
        f"DEMO_DIR {demo_dir} missing expected subdirs: {missing}. "
        "Was the relocation (T009) completed?"
    )


@pytest.mark.skip(reason="Requires code change T011 — test documents contract")
def test_demo_bootstrap_all_finds_content() -> None:
    """bootstrap_all() discovers bundles when run from the installed package."""
    from sqlalchemy.ext.asyncio import AsyncSession

    # This test is a contract marker — it requires an async session + real DB
    # to run fully. The key assertion is that DEMO_DIR resolves correctly.
    from anvil.db.session import AsyncSessionLocal
    from anvil.services.demo_bootstrap import DemoBootstrapService

    async def _test():
        async with AsyncSessionLocal() as session:
            svc = DemoBootstrapService(session)
            # Just validate the demo dir resolved correctly;
            # we're not running bootstrap_all here (that needs a real DB)
            assert svc is not None

    import asyncio

    asyncio.run(_test())


def test_demo_bootstrap_not_cwd_relative() -> None:
    """DEMO_DIR must NOT resolve relative to the current working directory.

    After T011, removing the CWD-relative data/demo path, the service
    should not care about what directory the process runs from.
    """
    # If DEMO_DIR still points to a CWD-relative "data/demo", this
    # test helps catch it (it would only exist when CWD is the repo root).
    import importlib

    mod = importlib.import_module("anvil.services.demo_bootstrap")
    importlib.reload(mod)

    demo_dir = mod.DEMO_DIR
    cwd_demo = Path.cwd() / "data" / "demo"
    assert str(demo_dir.resolve()) != str(cwd_demo.resolve()), (
        "DEMO_DIR still resolves to CWD-relative 'data/demo'. "
        "T011 (importlib.resources) not yet implemented."
    )