#!/usr/bin/env python3
"""Verify the NMRG (Native-Mode Regression Gate) for spec 040.

Asserts that ``huggingface_hub`` is NOT importable through any path
used by the base (no-finestune) installation.  Run with::

    pip install anvil  # no extras
    python tests/e2e/test_nmrg_040.py

Or via::

    .venv/bin/python tests/e2e/test_nmrg_040.py

Expected exit code: 0 (success) when ``huggingface_hub`` is not installed.
"""

import sys


def main() -> None:
    """Run NMRG checks and exit with 0 on success, 1 on failure."""
    failures: list[str] = []

    # 1. huggingface_hub must NOT be importable from the base install.
    try:
        import huggingface_hub

        failures.append(
            "huggingface_hub IS importable — the [finetune] extra "
            "is leaking into the base install"
        )
    except ImportError:
        pass  # Expected — NMRG invariant holds.

    # 2. Core engine path must not pull in huggingface_hub.
    import anvil.core.engine

    for forbidden in ("huggingface_hub",):
        if forbidden in sys.modules:
            failures.append(
                f"{forbidden} was loaded by the stdlib core engine path"
            )

    # 3. The ModelSource implementations (with safe hf_source import-guard
    #    code) must compile without huggingface_hub installed.
    try:
        from anvil.services.model_import.hf_source import HfHubSource

        # The import itself must not load huggingface_hub.
        if "huggingface_hub" in sys.modules:
            failures.append(
                "Importing HfHubSource triggered huggingface_hub load"
            )

        # The availability check must return False.
        from anvil.services.model_import.hf_source import (
            _huggingface_hub_available,
        )

        if _huggingface_hub_available():
            failures.append(
                "_huggingface_hub_available() returned True when "
                "huggingface_hub is not installed"
            )
    except ImportError as exc:
        failures.append(f"Failed to import HfHubSource: {exc}")

    # 4. LocalSource must always resolve without any extra.
    try:
        from anvil.services.model_import.local_source import LocalSource
    except ImportError as exc:
        failures.append(f"Failed to import LocalSource: {exc}")

    if failures:
        print("NMRG FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        sys.exit(1)

    print("NMRG OK — huggingface_hub isolation verified")
    sys.exit(0)


if __name__ == "__main__":
    main()