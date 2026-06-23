# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Training start result model.

``TrainingStartResult`` captures the identifiers returned by the server
after a training run is successfully started.
"""

from __future__ import annotations

from pydantic import BaseModel


class TrainingStartResult(BaseModel):
    """Identifiers returned after starting a training run.

    Parameters
    ----------
    run_id : str
        Server-assigned run identifier for this training session.
    mlflow_run_id : str
        MLflow run identifier for experiment tracking.
    experiment_id : str
        MLflow experiment identifier.
    """

    run_id: str
    mlflow_run_id: str
    experiment_id: str