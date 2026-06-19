"""God class exposing all high-level application services.

Provides a single entry point for service access from CLI, route
handlers, and tests. All business logic flows through this surface;
no consumer directly instantiates a service (FR-018).

Services that need no per-request state are lazy properties.
Services that need an async :class:`AsyncSession <sqlalchemy.ext.asyncio.AsyncSession>`
are provided as factory methods or async context managers.
"""

from __future__ import annotations

from .services.inference.inference import InferenceService
from .services.tracking.tracking import TrackingService
from .services.training.export import SafetensorsExportService
from .services.training.training import TrainingService


class AnvilWorkbench:
    """God class exposing high-level application services.

    Provides a single entry point for service access from CLI and
    route handlers. Wraps all stateless services as lazy properties;
    session-dependent services are provided via factory methods.

    Parameters
    ----------
    _training : TrainingService
        Cached training service instance.
    _tracking : TrackingService or None
        Cached tracking service instance, created on first access.
    _inference : InferenceService or None
        Cached inference service instance, created on first access.
    _export : SafetensorsExportService or None
        Cached export service instance, created on first access.
    """

    def __init__(self) -> None:
        self._training = TrainingService()
        self._tracking: TrackingService | None = None
        self._inference: InferenceService | None = None
        self._export: SafetensorsExportService | None = None

    # -- Stateless services (lazy properties) -------------------------------

    @property
    def training(self) -> TrainingService:
        """Return the training service instance.

        Returns
        -------
        TrainingService
        """
        return self._training

    @property
    def tracking(self) -> TrackingService:
        """Return the MLflow experiment tracking service instance.

        Returns
        -------
        TrackingService
        """
        if self._tracking is None:
            self._tracking = TrackingService()
        return self._tracking

    @property
    def inference(self) -> InferenceService:
        """Return the inference / demo model service instance.

        Returns
        -------
        InferenceService
        """
        if self._inference is None:
            self._inference = InferenceService()
        return self._inference

    @property
    def export(self) -> SafetensorsExportService:
        """Return the safetensors model export service instance.

        Returns
        -------
        SafetensorsExportService
        """
        if self._export is None:
            self._export = SafetensorsExportService()
        return self._export


# Module-level singleton for import convenience.
workbench = AnvilWorkbench()