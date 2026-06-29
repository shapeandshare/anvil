# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Service for the HuggingFace Model Browser — catalog loading, resource
eligibility, and runnable-status checks.

``ModelBrowserService`` loads a curated YAML catalog of small models,
computes hardware eligibility for local execution, and provides accessor
methods for architecture allow-lists, accepted formats, and catalog
membership queries.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

import psutil
import yaml  # type: ignore[import-untyped]

from ...gpu import GpuInfo, detect_gpu
from .._shared.runnable_status import RunnableStatus
from ..model_import.model_import_service import (
    _ACCEPTED_FORMATS,
    _ALLOWED_ARCHITECTURES,
)
from .catalog_entry import CatalogEntry
from .curated_catalog import CuratedCatalog
from .resource_envelope import ResourceEnvelope

logger = logging.getLogger(__name__)


class ModelBrowserService:
    """Loads and queries the curated model browser catalog.

    Wraps a YAML-backed catalog of curated HuggingFace models with
    methods for hardware eligibility assessment, runnable-status
    determination against the spec 040 allow-list, and resource
    detection on the host system.

    Parameters
    ----------
    catalog_path : str or None, optional
        Path to the curated-models YAML file. When ``None`` (default),
        the service resolves the path relative to the installed package
        at ``anvil/data/curated-models.yaml``.
    """

    def __init__(self, catalog_path: str | None = None) -> None:
        """Initialise the model browser service.

        Parameters
        ----------
        catalog_path : str or None, optional
            Override path to the curated-models YAML file. Defaults to
            the bundled ``anvil/data/curated-models.yaml``.
        """
        if catalog_path is not None:
            self._catalog_path = Path(catalog_path)
        else:
            self._catalog_path = (
                Path(__file__).resolve().parent.parent.parent
                / "data"
                / "curated-models.yaml"
            )
        self._catalog: CuratedCatalog | None = None

    def _load_catalog(self) -> CuratedCatalog:
        """Read, parse, and validate the curated-models YAML file.

        Loads the YAML file at ``_catalog_path``, parses it with
        PyYAML, and validates the structure against the
        ``CuratedCatalog`` Pydantic model. The result is cached so
        subsequent calls return the same object.

        Returns
        -------
        CuratedCatalog
            The validated catalog of curated model entries.

        Raises
        ------
        FileNotFoundError
            If the YAML file does not exist at ``_catalog_path``.
        yaml.YAMLError
            If the file contains invalid YAML.
        pydantic.ValidationError
            If the parsed YAML does not match the ``CuratedCatalog``
            schema.
        """
        if self._catalog is not None:
            return self._catalog

        logger.info("Loading curated model catalog from %s", self._catalog_path)
        path = self._catalog_path
        if not path.exists():
            raise FileNotFoundError(f"Catalog file not found: {path}")

        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)

        self._catalog = CuratedCatalog.model_validate(raw)
        return self._catalog

    @property
    def catalog(self) -> list[CatalogEntry]:
        """Return the list of curated model entries.

        Lazily loads and caches the catalog on first access.

        Returns
        -------
        list[CatalogEntry]
            Ordered list of curated model entries from the YAML
            catalog.
        """
        return list(self._load_catalog().catalog)

    @staticmethod
    def check_eligibility(
        envelope: ResourceEnvelope,
        gpu: GpuInfo,
        ram_total_gb: float,
    ) -> bool:
        """Determine whether the host has sufficient resources for a model.

        Compares available system RAM against the model's minimum
        requirement and, when a GPU is available with a recognised
        backend, checks VRAM against the per-backend threshold.

        Parameters
        ----------
        envelope : ResourceEnvelope
            Hardware resource requirements for the candidate model.
        gpu : GpuInfo
            Detected GPU capabilities of the host system.
        ram_total_gb : float
            Total system RAM in gigabytes.

        Returns
        -------
        bool
            ``True`` if the host meets the resource requirements;
            ``False`` otherwise.
        """
        if ram_total_gb < envelope.min_ram_gb:
            return False

        if gpu.available and gpu.backend is not None:
            key = str(gpu.backend)
            required = envelope.min_vram_per_backend.get(key)
            if required is not None and gpu.memory_total_gb is not None:
                if gpu.memory_total_gb < required:
                    return False

        return True

    @staticmethod
    def runnable_status(architecture: str) -> str:
        """Return the runnable status for a model architecture.

        Checks membership in the approved architecture allow-list
        (spec 040). Returns ``"runnable"`` for allowed architectures
        and ``"track_only"`` for all others.

        Parameters
        ----------
        architecture : str
            HuggingFace architecture class name (e.g.
            ``"LlamaForCausalLM"``).

        Returns
        -------
        str
            ``"runnable"`` or ``"track_only"``, matching the
            ``RunnableStatus`` enum values.
        """
        if architecture in _ALLOWED_ARCHITECTURES:
            return str(RunnableStatus.RUNNABLE)
        return str(RunnableStatus.TRACK_ONLY)

    @staticmethod
    def accepted_format() -> str:
        """Return the sole accepted model format.

        Mirrors the single-element set from spec 040's
        ``_ACCEPTED_FORMATS``.

        Returns
        -------
        str
            The accepted format identifier, currently
            ``"safetensors"``.
        """
        # _ACCEPTED_FORMATS is a frozenset with exactly one element.
        # next(iter(...)) returns that element without materialising a
        # temporary data structure.
        return next(iter(_ACCEPTED_FORMATS))

    def is_catalog_model(self, hf_id: str) -> bool:
        """Check whether a HuggingFace ID is in the curated catalog.

        Performs a case-sensitive membership check against all
        ``hf_id`` values in the loaded catalog.

        Parameters
        ----------
        hf_id : str
            HuggingFace model identifier (e.g.
            ``"TinyLlama/TinyLlama-1.1B-Chat-v1.0"``).

        Returns
        -------
        bool
            ``True`` if the ID is present in the catalog; ``False``
            otherwise.
        """
        return any(entry.hf_id == hf_id for entry in self.catalog)

    @staticmethod
    def hf_available() -> bool:
        """Return whether the optional ``huggingface_hub`` dependency is present.

        Uses ``importlib.util.find_spec`` to detect the package without
        importing it, preserving the base-install invariant that
        ``huggingface_hub`` is never imported unless the ``[finetune]``
        extra is installed.

        Returns
        -------
        bool
            ``True`` when ``huggingface_hub`` is importable (the
            ``[finetune]`` extra is installed); ``False`` otherwise.
        """
        return importlib.util.find_spec("huggingface_hub") is not None

    @staticmethod
    def detect_resources() -> tuple[GpuInfo, float]:
        """Detect the host system's GPU and RAM resources.

        Calls ``detect_gpu()`` for GPU information and ``psutil`` for
        total system RAM. This is a convenience wrapper that returns
        both values in a single call.

        Returns
        -------
        tuple[GpuInfo, float]
            A ``(gpu_info, ram_total_gb)`` pair where ``gpu_info`` is
            the detected GPU capabilities and ``ram_total_gb`` is the
            total system RAM in gigabytes.
        """
        gpu_info = detect_gpu()
        ram_total_gb = psutil.virtual_memory().total / (1024**3)
        return (gpu_info, ram_total_gb)
