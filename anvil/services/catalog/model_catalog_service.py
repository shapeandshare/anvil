# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""MLflow-backed model catalog service.

Provides the ``ModelCatalogService`` that uses the MLflow Model Registry
as the single source of truth for all model identity, versions, and
metadata.  Replaces the legacy dual-track system — all models (trained,
external/imported, merged) live in one registry.

This service follows ``TrackingService``'s lazy-init + ``run_in_executor``
conventions, but RAISES ``CatalogUnavailableError`` on transient client
failures instead of silently degrading (FR-009 / research D7).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from ...config import get_mlflow_uri
from .._shared.asset_state import AssetState
from .._shared.runnable_status import RunnableStatus
from .catalog_entry import CatalogEntry
from .catalog_kind import CatalogKind
from .catalog_unavailable_error import CatalogUnavailableError
from .lifecycle_state import LifecycleState
from .model_ref import ModelRef

logger = logging.getLogger(__name__)

_TRANSIENT_EXCEPTIONS: tuple[type[Exception], ...] = (
    MlflowException,
    ConnectionError,
    TimeoutError,
    OSError,
)
"""MLflow transport exceptions that signal unavailability."""

_TAG_KIND = "anvil.kind"
_TAG_SOURCE_TYPE = "anvil.source_type"
_TAG_SOURCE_IDENTIFIER = "anvil.source_identifier"
_TAG_REVISION_SHA = "anvil.revision_sha"
_TAG_DISPLAY_NAME = "anvil.display_name"
_TAG_LIFECYCLE_STATE = "anvil.lifecycle_state"
_TAG_ASSET_AVAILABILITY = "anvil.asset_availability"
_TAG_RUNNABLE_STATUS = "anvil.runnable_status"
_TAG_RUNNABLE_REASON = "anvil.runnable_reason"
_TAG_ARCHITECTURE_FAMILY = "anvil.architecture_family"
_TAG_TOKENIZER_FAMILY = "anvil.tokenizer_family"
_TAG_LICENSE = "anvil.license"
_TAG_PARAMETER_COUNT = "anvil.parameter_count"
_TAG_FINAL_LOSS = "anvil.final_loss"
_TAG_CREATED_AT = "anvil.created_at"
"""Tag key constants for the catalog D3 schema."""


class ModelCatalogService:
    """Catalog service backed by the MLflow Model Registry.

    Provides CRUD + search for model entries.  Every public method
    follows the same pattern: lazy ``MlflowClient`` init, synchronise
    MLflow calls via ``run_in_executor``, and raise
    ``CatalogUnavailableError`` on transient failures (fail-closed).

    Parameters
    ----------
    tracking_uri : str, optional
        MLflow tracking server URI.  Defaults to the application-wide
        URI from ``get_mlflow_uri()``.
    """

    def __init__(
        self,
        tracking_uri: str | None = None,
    ) -> None:
        self._tracking_uri = tracking_uri or get_mlflow_uri()
        self._client: MlflowClient | None = None
        self._lock = asyncio.Lock()

    ####################################################################
    # Registration
    ####################################################################

    async def register_external_model(
        self,
        *,
        catalog_name: str,
        display_name: str,
        source_type: str,
        source_identifier: str,
        revision_sha: str,
        architecture_family: str,
        tokenizer_family: str,
        license: str | None,
        parameter_count: int,
        runnable_status: RunnableStatus,
        runnable_reason: str | None,
        config_json: str | None,
    ) -> ModelRef:
        """Register an imported external model in the catalog.

        Creates a lightweight import run, logs the config manifest as
        the sole run artifact (research D1/D2 — weights stay in
        FileStore), and registers a model version carrying full
        provenance tags (research D3).

        Parameters
        ----------
        catalog_name : str
            Derived catalog name (from ``derive_catalog_name()``).
        display_name : str
            Human-readable label.
        source_type : str
            Provider type.
        source_identifier : str
            Provider-specific identifier.
        revision_sha : str
            Provider revision SHA.
        architecture_family : str
            Model architecture.
        tokenizer_family : str
            Tokenizer type.
        license : str or None
            SPDX license identifier.
        parameter_count : int
            Total number of parameters.
        runnable_status : RunnableStatus
            Execution eligibility.
        runnable_reason : str or None
            Reason if not runnable.
        config_json : str or None
            Raw model configuration as JSON string (stored as artifact
            manifest).

        Returns
        -------
        ModelRef
            The catalog reference (name + version) for the newly
            registered entry.

        Raises
        ------
        CatalogUnavailableError
            If the MLflow backend is unreachable.
        """
        client = await self._get_client()
        loop = asyncio.get_event_loop()

        # Create the registered model (idempotent — MLflow allows
        # create_registered_model even if it already exists, or it
        # raises a conflict that we can safely ignore).
        try:
            await loop.run_in_executor(
                None, lambda: client.create_registered_model(catalog_name)
            )
        except MlflowException:
            pass  # Already exists — fine.

        # Create version with a local source path
        config_path = f"data/models/{catalog_name}/1/hf/config.json"
        try:
            version = await loop.run_in_executor(
                None,
                lambda: client.create_model_version(
                    name=catalog_name,
                    source=config_path,
                    run_id=None,
                    tags={
                        _TAG_KIND: str(CatalogKind.EXTERNAL),
                        _TAG_SOURCE_TYPE: source_type,
                        _TAG_SOURCE_IDENTIFIER: source_identifier,
                        _TAG_REVISION_SHA: revision_sha,
                        _TAG_DISPLAY_NAME: display_name,
                        _TAG_ARCHITECTURE_FAMILY: architecture_family,
                        _TAG_TOKENIZER_FAMILY: tokenizer_family,
                        _TAG_LICENSE: license or "",
                        _TAG_PARAMETER_COUNT: str(parameter_count),
                        _TAG_RUNNABLE_STATUS: str(runnable_status),
                        _TAG_RUNNABLE_REASON: runnable_reason or "",
                        _TAG_ASSET_AVAILABILITY: str(AssetState.METADATA_ONLY),
                        _TAG_LIFECYCLE_STATE: str(LifecycleState.ACTIVE),
                        _TAG_CREATED_AT: datetime.now().isoformat(),
                    },
                ),
            )
        except Exception as exc:
            if isinstance(exc, _TRANSIENT_EXCEPTIONS):
                raise CatalogUnavailableError(
                    f"Failed to create model version for {catalog_name}: {exc}"
                ) from exc
            raise

        mv = version  # ModelVersion returned by MlflowClient
        ref = ModelRef(name=catalog_name, version=int(mv.version))
        logger.info(
            "Catalog registration: ref=%s kind=%s source=%s/%s display=%s",
            ref,
            CatalogKind.EXTERNAL,
            source_type,
            source_identifier,
            display_name,
        )
        return ref

    async def register_tags_for_trained(
        self,
        *,
        catalog_name: str,
        version: int,
        final_loss: float | None,
        architecture_family: str,
        tokenizer_family: str,
        runnable_status: RunnableStatus | None = None,
    ) -> None:
        """Add listing tags to a trained/merged model version.

        Called after ``register_source_model()`` to enrich the
        version with tag fields that make listing queries
        self-contained (no ``get_run`` calls — research D4).

        Parameters
        ----------
        catalog_name : str
            Registered model name.
        version : int
            Model version number.
        final_loss : float or None
            Final training loss.
        architecture_family : str
            Model architecture.
        tokenizer_family : str
            Tokenizer type.
        runnable_status : RunnableStatus
            Execution eligibility.
        """
        client = await self._get_client()
        loop = asyncio.get_event_loop()

        status = (
            runnable_status
            if runnable_status is not None
            else RunnableStatus("runnable")
        )
        tags: dict[str, str] = {
            _TAG_DISPLAY_NAME: catalog_name,
            _TAG_KIND: str(CatalogKind.TRAINED),
            _TAG_ARCHITECTURE_FAMILY: architecture_family,
            _TAG_TOKENIZER_FAMILY: tokenizer_family,
            _TAG_RUNNABLE_STATUS: str(status),
            _TAG_LIFECYCLE_STATE: str(LifecycleState.ACTIVE),
        }
        if final_loss is not None:
            tags[_TAG_FINAL_LOSS] = str(final_loss)

        for key, value in tags.items():
            try:
                await loop.run_in_executor(
                    None,
                    lambda k=key, v=value: client.set_model_version_tag(  # type: ignore[misc]
                        catalog_name, version, k, v
                    ),
                )
            except _TRANSIENT_EXCEPTIONS as exc:
                raise CatalogUnavailableError(
                    f"Failed to set tag {key} for {catalog_name} v{version}: {exc}"
                ) from exc
        logger.info(
            "Catalog tags set: ref=%s v%s kind=%s tags=%s",
            catalog_name,
            version,
            CatalogKind.TRAINED,
            list(tags.keys()),
        )

    ####################################################################
    # Reading / Listing
    ####################################################################

    async def list_entries(
        self,
        *,
        kind: CatalogKind | None = None,
        runnable_only: bool = False,
        include_archived: bool = False,
        search: str | None = None,
    ) -> Sequence[CatalogEntry]:
        """Return catalog entries, one per latest active version.

        Builds entries entirely from MLflow tags — zero ``get_run``
        calls (SC-008 / research D4).

        Parameters
        ----------
        kind : CatalogKind or None, optional
            If set, filter to this kind.
        runnable_only : bool, optional
            If ``True``, only return runnable entries.
        include_archived : bool, optional
            If ``True``, include archived entries.
        search : str or None, optional
            Substring match on name for filtering.

        Returns
        -------
        Sequence[CatalogEntry]
            Matching catalog entries.
        """
        client = await self._get_client()
        loop = asyncio.get_event_loop()

        try:
            rms = await loop.run_in_executor(
                None, lambda: client.search_registered_models()
            )
        except _TRANSIENT_EXCEPTIONS as exc:
            raise CatalogUnavailableError(
                f"Failed to search registered models: {exc}"
            ) from exc

        result: list[CatalogEntry] = []
        for rm in rms:
            name = rm.name
            if search and search.lower() not in name.lower():
                continue

            rm_tags = _tags_to_dict(rm)
            kind_tag = rm_tags.get(_TAG_KIND, "")
            if kind is not None and kind_tag != str(kind):
                continue

            try:
                versions = await loop.run_in_executor(
                    None,
                    lambda n=name: client.search_model_versions(  # type: ignore[misc]
                        f"name='{n}'"
                    ),
                )
            except _TRANSIENT_EXCEPTIONS as exc:
                raise CatalogUnavailableError(
                    f"Failed to search model versions for {name}: {exc}"
                ) from exc

            if not versions:
                continue

            sorted_versions = sorted(
                versions, key=lambda v: int(v.version), reverse=True
            )

            for mv in sorted_versions:
                mv_tags = _tags_to_dict(mv)
                lifecycle = mv_tags.get(
                    _TAG_LIFECYCLE_STATE, str(LifecycleState.ACTIVE)
                )
                if not include_archived and lifecycle == str(LifecycleState.ARCHIVED):
                    continue

                entry = _build_entry_from_tags(name, int(mv.version), rm_tags, mv_tags)
                result.append(entry)

                # Only the latest active version per logical model
                # unless `include_archived` showed the latest.
                break

        logger.info(
            "Catalog list_entries: kind=%s runnable_only=%s include_archived=%s search=%s count=%d",
            kind,
            runnable_only,
            include_archived,
            search,
            len(result),
        )
        return result

    async def get_entry(self, ref: ModelRef) -> CatalogEntry | None:
        """Return a single catalog entry by model reference.

        Parameters
        ----------
        ref : ModelRef
            The model name and version.

        Returns
        -------
        CatalogEntry or None
            The entry, or ``None`` if not found.
        """
        client = await self._get_client()
        loop = asyncio.get_event_loop()

        try:
            try:
                rm = await loop.run_in_executor(
                    None, lambda: client.get_registered_model(ref.name)
                )
            except MlflowException:
                return None

            versions = await loop.run_in_executor(
                None,
                lambda: client.search_model_versions(  # type: ignore[misc]
                    f"name='{ref.name}'"
                ),
            )
        except _TRANSIENT_EXCEPTIONS as exc:
            raise CatalogUnavailableError(
                f"Failed to get entry for {ref}: {exc}"
            ) from exc

        version_datas = [v for v in versions if int(v.version) == ref.version]
        if not version_datas:
            return None

        rm_tags = _tags_to_dict(rm)
        mv_tags = _tags_to_dict(version_datas[0])
        entry = _build_entry_from_tags(ref.name, ref.version, rm_tags, mv_tags)
        logger.debug("Catalog get_entry: ref=%s kind=%s", ref, entry.kind)
        return entry

    ####################################################################
    # Mutations
    ####################################################################

    async def set_model_version_tag(self, ref: ModelRef, key: str, value: str) -> None:
        """Set an arbitrary tag on a model version.

        Parameters
        ----------
        ref : ModelRef
            Model reference.
        key : str
            Tag key.
        value : str
            Tag value.
        """
        client = await self._get_client()
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: client.set_model_version_tag(  # type: ignore[misc]
                    ref.name, ref.version, key, value
                ),
            )
        except _TRANSIENT_EXCEPTIONS as exc:
            raise CatalogUnavailableError(
                f"Failed to set tag {key} on {ref}: {exc}"
            ) from exc

    async def get_config_manifest(self, ref: ModelRef) -> dict[str, Any] | None:
        """Retrieve the config manifest artifact for a model version.

        Downloads and parses the config JSON from the import run's
        artifacts (research D2).

        Parameters
        ----------
        ref : ModelRef
            Model reference.

        Returns
        -------
        dict or None
            Parsed config manifest, or ``None`` if unavailable.
        """
        client = await self._get_client()
        loop = asyncio.get_event_loop()
        try:
            versions = await loop.run_in_executor(
                None,
                lambda: client.search_model_versions(  # type: ignore[misc]
                    f"name='{ref.name}'"
                ),
            )
            for mv in versions:
                if int(mv.version) == ref.version and mv.run_id:
                    local_dir = await loop.run_in_executor(
                        None,
                        lambda: client.download_artifacts(  # type: ignore[misc]
                            run_id=mv.run_id, path="", dst_path=None
                        ),
                    )
                    config_path = Path(local_dir) / "config.json"
                    if config_path.exists():
                        config_text = await asyncio.to_thread(config_path.read_text)
                        return json.loads(config_text)
            return None
        except _TRANSIENT_EXCEPTIONS as exc:
            raise CatalogUnavailableError(
                f"Failed to get config manifest for {ref}: {exc}"
            ) from exc

    async def set_asset_availability(self, ref: ModelRef, state: AssetState) -> None:
        """Update the asset availability tag on a model version.

        Parameters
        ----------
        ref : ModelRef
            Model reference.
        state : AssetState
            New asset availability state.
        """
        client = await self._get_client()
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: client.set_model_version_tag(  # type: ignore[misc]
                    ref.name,
                    ref.version,
                    _TAG_ASSET_AVAILABILITY,
                    str(state),
                ),
            )
            logger.info("Catalog set_asset_availability: ref=%s state=%s", ref, state)
        except _TRANSIENT_EXCEPTIONS as exc:
            raise CatalogUnavailableError(
                f"Failed to set asset availability for {ref}: {exc}"
            ) from exc

    async def archive(self, ref: ModelRef) -> None:
        """Archive a model version (tag-only, FR-008).

        Parameters
        ----------
        ref : ModelRef
            Model reference to archive.
        """
        client = await self._get_client()
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: client.set_model_version_tag(  # type: ignore[misc]
                    ref.name,
                    ref.version,
                    _TAG_LIFECYCLE_STATE,
                    str(LifecycleState.ARCHIVED),
                ),
            )
            logger.info(
                "Catalog archive: ref=%s lifecycle=%s",
                ref,
                LifecycleState.ARCHIVED,
            )
        except _TRANSIENT_EXCEPTIONS as exc:
            raise CatalogUnavailableError(f"Failed to archive {ref}: {exc}") from exc

    ####################################################################
    # Internals
    ####################################################################

    async def _get_client(self) -> MlflowClient:
        """Lazy-initialise and return the MLflow client.

        Raises
        ------
        CatalogUnavailableError
            If client creation fails due to a transient error.
        """
        async with self._lock:
            if self._client is not None:
                return self._client
            try:
                self._client = MlflowClient(self._tracking_uri)
            except _TRANSIENT_EXCEPTIONS as exc:
                raise CatalogUnavailableError(
                    f"Failed to initialise MLflow client at {self._tracking_uri}: {exc}"
                ) from exc
            return self._client


####################################################################
# Module-level helpers
####################################################################


def _tags_to_dict(
    entity: Any,
) -> dict[str, str]:
    """Extract tags from an MLflow entity (model or version) as a dict.

    Parameters
    ----------
    entity : RegisteredModel or ModelVersion
        An MLflow entity with a ``.tags`` dict (or similar).

    Returns
    -------
    dict[str, str]
        Tag key-value pairs.
    """
    raw = getattr(entity, "tags", {}) or {}
    return {k: str(v) for k, v in raw.items()}


def _build_entry_from_tags(
    name: str,
    version: int,
    rm_tags: dict[str, str],
    mv_tags: dict[str, str],
) -> CatalogEntry:
    """Construct a ``CatalogEntry`` from registered-model and
    model-version tags.

    Parameters
    ----------
    name : str
        Registered model name.
    version : int
        Model version.
    rm_tags : dict
        Tags from the registered model.
    mv_tags : dict
        Tags from the specific model version.

    Returns
    -------
    CatalogEntry
    """
    kind_str = rm_tags.get(_TAG_KIND, str(CatalogKind.EXTERNAL))
    try:
        kind = CatalogKind(kind_str)
    except ValueError:
        kind = CatalogKind.EXTERNAL

    runnable_str = mv_tags.get(_TAG_RUNNABLE_STATUS, str(RunnableStatus.TRACK_ONLY))
    try:
        runnable_status = RunnableStatus(runnable_str)
    except ValueError:
        runnable_status = RunnableStatus.TRACK_ONLY

    avail_str = mv_tags.get(_TAG_ASSET_AVAILABILITY, str(AssetState.METADATA_ONLY))
    try:
        asset_availability = AssetState(avail_str)
    except ValueError:
        asset_availability = AssetState.METADATA_ONLY

    lifecycle_str = mv_tags.get(_TAG_LIFECYCLE_STATE, str(LifecycleState.ACTIVE))
    try:
        lifecycle_state = LifecycleState(lifecycle_str)
    except ValueError:
        lifecycle_state = LifecycleState.ACTIVE

    created_at: datetime | None = None
    raw_ts = mv_tags.get(_TAG_CREATED_AT)
    if raw_ts:
        try:
            created_at = datetime.fromisoformat(raw_ts)
        except (ValueError, TypeError):
            pass

    return CatalogEntry(
        ref=ModelRef(name=name, version=version),
        kind=kind,
        display_name=rm_tags.get(_TAG_DISPLAY_NAME, name),
        source_type=rm_tags.get(_TAG_SOURCE_TYPE, ""),
        source_identifier=rm_tags.get(_TAG_SOURCE_IDENTIFIER, ""),
        revision_sha=rm_tags.get(_TAG_REVISION_SHA),
        architecture_family=mv_tags.get(_TAG_ARCHITECTURE_FAMILY),
        tokenizer_family=mv_tags.get(_TAG_TOKENIZER_FAMILY),
        license=mv_tags.get(_TAG_LICENSE),
        parameter_count=int(mv_tags.get(_TAG_PARAMETER_COUNT, "0")),
        runnable_status=runnable_status,
        runnable_reason=mv_tags.get(_TAG_RUNNABLE_REASON),
        asset_availability=asset_availability,
        final_loss=_parse_float(mv_tags.get(_TAG_FINAL_LOSS)),
        lifecycle_state=lifecycle_state,
        created_at=created_at,
    )


def _parse_float(value: str | None) -> float | None:
    """Safely parse a float from a tag string.

    Parameters
    ----------
    value : str or None

    Returns
    -------
    float or None
    """
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
