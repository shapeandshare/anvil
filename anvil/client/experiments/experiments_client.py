# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Experiments client — domain aggregator for experiment tracking operations.

``ExperimentsClient`` provides a single entry point for all experiment
operations: list, get, compare, get_metrics, delete, list_artifacts, and
download_artifact. It delegates each operation to its corresponding command
class.
"""

from __future__ import annotations

from .._shared.transport import Transport
from .experiment_artifacts_command import ExperimentArtifactsCommand
from .experiment_compare_command import ExperimentCompareCommand
from .experiment_delete_command import ExperimentDeleteCommand
from .experiment_download_command import ExperimentDownloadCommand
from .experiment_get_command import ExperimentGetCommand
from .experiment_list_command import ExperimentListCommand
from .experiment_metrics_command import ExperimentMetricsCommand


class ExperimentsClient:
    """Experiment tracking operations.

    Aggregates all experiment commands behind a single facade. Each public
    method maps to one server API operation.

    Parameters
    ----------
    transport : Transport
        The shared SDK transport instance.
    """

    def __init__(self, transport: Transport) -> None:
        self._list_cmd = ExperimentListCommand(transport)
        self._get_cmd = ExperimentGetCommand(transport)
        self._compare_cmd = ExperimentCompareCommand(transport)
        self._metrics_cmd = ExperimentMetricsCommand(transport)
        self._delete_cmd = ExperimentDeleteCommand(transport)
        self._artifacts_cmd = ExperimentArtifactsCommand(transport)
        self._download_cmd = ExperimentDownloadCommand(transport)

    async def list(self) -> list[dict[str, object]]:
        """List all experiments.

        Returns
        -------
        list[dict[str, object]]
            A list of experiment records.
        """
        return await self._list_cmd.execute()

    async def get(self, experiment_id: str) -> dict[str, object]:
        """Get a single experiment by its identifier.

        Parameters
        ----------
        experiment_id : str
            The unique experiment identifier.

        Returns
        -------
        dict[str, object]
            The experiment record.
        """
        return await self._get_cmd.execute(experiment_id)

    async def compare(self, *ids: str) -> dict[str, object]:
        """Compare multiple experiments side-by-side.

        Parameters
        ----------
        *ids : str
            One or more experiment identifiers to compare.

        Returns
        -------
        dict[str, object]
            Comparison data keyed by experiment identifier.
        """
        return await self._compare_cmd.execute(*ids)

    async def get_metrics(self, experiment_id: str) -> dict[str, object]:
        """Fetch metrics for the given experiment.

        Parameters
        ----------
        experiment_id : str
            The unique experiment identifier.

        Returns
        -------
        dict[str, object]
            Metrics data keyed by metric name.
        """
        return await self._metrics_cmd.execute(experiment_id)

    async def delete(self, experiment_id: str) -> dict[str, object]:
        """Delete an experiment.

        Parameters
        ----------
        experiment_id : str
            The unique experiment identifier.

        Returns
        -------
        dict[str, object]
            A response payload confirming the deletion.
        """
        return await self._delete_cmd.execute(experiment_id)

    async def list_artifacts(
        self, experiment_id: str, run_id: str,
    ) -> dict[str, object]:
        """List artifacts for a specific run.

        Parameters
        ----------
        experiment_id : str
            The experiment identifier.
        run_id : str
            The run identifier within the experiment.

        Returns
        -------
        dict[str, object]
            Artifact listing data.
        """
        return await self._artifacts_cmd.execute(experiment_id, run_id)

    async def download_artifact(
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
        return await self._download_cmd.execute(
            experiment_id, run_id, path, dest=dest,
        )