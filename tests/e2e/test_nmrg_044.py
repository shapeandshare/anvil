#!/usr/bin/env python3
"""Verify the NMRG (Native-Mode Regression Gate) for spec 044.

Asserts that ``peft``, ``bitsandbytes``, ``datasets``, and ``accelerate``
are NOT importable through any path used by the base (no-finestune)
installation.  Run with::

    pip install anvil  # no extras
    python tests/e2e/test_nmrg_044.py

Or via::

    .venv/bin/python tests/e2e/test_nmrg_044.py

Expected exit code: 0 (success) when no finetune deps are installed.
"""

import sys


def main() -> None:
    """Run NMRG checks and exit with 0 on success, 1 on failure."""
    failures: list[str] = []

    # 1. Forbidden packages must NOT be importable from the base install.
    forbidden_packages = ("peft", "bitsandbytes", "datasets", "accelerate")
    for pkg in forbidden_packages:
        try:
            __import__(pkg)
            failures.append(
                f"{pkg} IS importable — the [finetune] extra "
                "is leaking into the base install"
            )
        except ImportError:
            pass  # Expected — NMRG invariant holds.

    # 2. Core engine path must not pull in any finetune deps.
    import anvil.core.engine

    for pkg in forbidden_packages:
        if pkg in sys.modules:
            failures.append(f"{pkg} was loaded by the stdlib core engine path")

    # 3. The LocalLoraBackend module must compile (import) without
    #    loading any finetune deps (they are guarded by try/except
    #    ImportError at runtime).
    from anvil.services.compute.local_lora_backend import LocalLoraBackend

    for pkg in forbidden_packages:
        if pkg in sys.modules:
            failures.append(f"Importing LocalLoraBackend triggered {pkg} load")

    # 4. is_available() must return False when deps are not installed.
    if LocalLoraBackend.is_available():
        failures.append(
            "LocalLoraBackend.is_available() returned True when "
            "peft/torch are not installed"
        )

    if failures:
        print("NMRG FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        sys.exit(1)

    print("NMRG OK — peft/bitsandbytes/datasets/accelerate " "isolation verified")
    sys.exit(0)


if __name__ == "__main__":
    main()
