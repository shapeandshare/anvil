# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Seed the demo model for API e2e tests.

Creates the demo model file at ``data/models/demo/model.json`` and a
matching experiment artifact so the inference service's
``_resolve_default_id`` path resolves correctly.

Resolution order:
1. If MLflow has a registered "demo" model, save to its experiment ID
2. Otherwise save to ``experiment_1.json`` (canonical fallback path)
"""

import asyncio
import shutil
import sys
from pathlib import Path

from anvil.services.inference.demo_model_provider import _train_demo_model

DEMO_MODEL_PATH = Path("data/models/demo/model.json")


def _get_mlflow_model_id() -> int | None:
    """Query MLflow for the "demo" model's experiment ID.

    Returns
    -------
    int or None
        The experiment ID if found, ``None`` otherwise.
    """
    try:
        from mlflow.tracking import MlflowClient
        client = MlflowClient("http://127.0.0.1:5001")
        models = client.search_registered_models()
        for m in models:
            if m.name == "demo":
                # Get the latest version's run and find its experiment_id
                for v in m.latest_versions:
                    run = client.get_run(v.run_id)
                    exp_id = run.data.tags.get("anvil.experiment_id")
                    if exp_id is not None:
                        return int(exp_id)
                    # Fallback: use the experiment ID from the run
                    return int(run.info.experiment_id)
    except Exception:
        pass
    return None


def _get_tracking_service_id() -> int | None:
    """Query the TrackingService (in-process fallback).

    Returns
    -------
    int or None
        The experiment ID if found, ``None`` otherwise.
    """
    try:
        from anvil.services.tracking.tracking import TrackingService
        svc = TrackingService()
        models = asyncio.run(svc.list_registered_models())
        for m in models:
            if m.get("name") == "demo" and m.get("id") is not None:
                return int(m["id"])
    except Exception:
        pass
    return None


def main() -> None:
    print("Training demo model (tiny, 400 steps)...", flush=True)
    _train_demo_model()

    if not DEMO_MODEL_PATH.exists():
        print(f"ERROR: demo model not saved at {DEMO_MODEL_PATH}", flush=True)
        sys.exit(1)

    # Determine the correct experiment ID from MLflow if available
    experiment_id = _get_mlflow_model_id()
    if experiment_id is None:
        experiment_id = _get_tracking_service_id()
    if experiment_id is None:
        experiment_id = 1

    experiment_path = Path(f"data/models/experiment_{experiment_id}.json")
    if not experiment_path.exists():
        shutil.copy2(str(DEMO_MODEL_PATH), str(experiment_path))
        print(f"Experiment artifact created at {experiment_path}", flush=True)
    else:
        print(f"Experiment artifact already exists at {experiment_path}", flush=True)

    print("Demo model seed complete.", flush=True)


if __name__ == "__main__":
    main()
