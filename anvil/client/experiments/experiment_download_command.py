# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Experiment download command — download a run artifact.

``ExperimentDownloadCommand`` downloads a specific artifact file from a run
within an experiment via ``GET /v1/experiments/{eid}/runs/{rid}/download``.
"""

from __future__ import annotations

from pathlib import Path

from .._shared.abstract_command import AbstractCommand


class ExperimentDownloadCommand(AbstractCommand):
    """Download a run artifact — ``GET /v1/experiments/{eid}/runs/{rid}/download``."""

    async def execute(
        self,
        experiment_id: str,
        run_id: str,
        path: str,
        *,
        dest: str | None = None,
    ) -> bytes | str:
        """Download a specific artifact file from a run.

        Parameters
        ----------
        experiment_id : str
            The experiment identifier.
        run_id : str
            The run identifier within the experiment.
        path : str
            Path of the artifact within the run to download.
        dest : str | None, optional
            Local file path to save the download to. If ``None``, returns
            raw bytes.

        Returns
        -------
        bytes | str
            ``bytes`` if ``dest`` is ``None``, otherwise the destination path
            as a string.
        """
        params = {"path": path}
        dest_path = Path(dest) if dest else None
        payload: bytes | Path = await self._transport.download(
            f"/v1/experiments/{experiment_id}/runs/{run_id}/download",
            dest=dest_path,
            params=params,
        )
        if isinstance(payload, Path):
            return str(payload)
        return payload