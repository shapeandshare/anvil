"""Lineage service — tracks MLflow run ↔ content version linkage.

Records which MLflow training runs consumed which exact content
version snapshot, enabling full experiment reproducibility and
lineage tracing from trained model back to source data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...db.repositories.content_versions import (
        ContentVersionRepository,
    )


class LineageService:
    """Tracks provenance links between MLflow training runs and content
    version snapshots.

    Each link (``VersionRunRef``) records the ``version_id``, the MLflow
    run's UUID, and a denormalised ``corpus_ref`` for quick queries.

    Parameters
    ----------
    version_repo : ContentVersionRepository
        Repository providing ``add_run_ref`` and ``get_run_refs`` methods.
    """

    def __init__(self, version_repo: ContentVersionRepository) -> None:
        """Initialise the lineage service.

        Parameters
        ----------
        version_repo : ContentVersionRepository
            Repository bound to an async SQLAlchemy session.
        """
        self._version_repo = version_repo

    async def record_run_ref(
        self,
        version_id: int,
        mlflow_run_id: str,
        corpus_ref: str,
    ) -> None:
        """Record a linkage between an MLflow run and a content version.

        Creates a ``VersionRunRef`` row via the repository so that
        experiments can be traced back to the exact content snapshot.

        Parameters
        ----------
        version_id : int
            Primary key of the ``ContentVersion`` the run consumed.
        mlflow_run_id : str
            MLflow run UUID (as returned by ``TrackingService.start_run``).
        corpus_ref : str
            Denormalised corpus reference, typically ``"corpus:<slug>"``
            or ``"corpus:<id>"``.
        """
        from ...db.models.content_version_run_ref import VersionRunRef

        ref = VersionRunRef(
            version_id=version_id,
            mlflow_run_id=mlflow_run_id,
            corpus_ref=corpus_ref,
        )
        await self._version_repo.add_run_ref(ref)

    async def lineage(self, version_id: int) -> list[dict]:
        """Return the run lineage for a content version.

        Queries all ``VersionRunRef`` records linked to *version_id*
        and returns a list of dicts with ``mlflow_run_id`` and
        ``corpus_ref``.

        Parameters
        ----------
        version_id : int
            Primary key of the version whose lineage to fetch.

        Returns
        -------
        list[dict]
            Each dict contains ``mlflow_run_id`` (str) and
            ``corpus_ref`` (str).
        """
        refs = await self._version_repo.get_run_refs(version_id)
        return [
            {
                "mlflow_run_id": r.mlflow_run_id,
                "corpus_ref": r.corpus_ref,
            }
            for r in refs
        ]