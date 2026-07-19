# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Visual feedback annotation service.

Provides the ``FeedbackService`` class for managing feedback reports,
their annotations, and associated screenshot files. Acts as the
business logic layer between the API routes and the repository/store
layers.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from ...db.models.feedback_report import FeedbackReport
from ...db.repositories.feedback_repository import FeedbackRepository
from ...storage.local import LocalFileStore
from ...workspace.workspace_paths import WorkspacePaths


class FeedbackService:
    """Business logic for feedback report and annotation management.

    Wraps a ``FeedbackRepository`` and a ``LocalFileStore`` to provide
    higher-level operations: submitting reports with screenshot files,
    listing, updating status, deleting, and exporting report data.

    Parameters
    ----------
    repo : FeedbackRepository
        Repository for feedback report persistence.
    store : LocalFileStore
        File store for screenshot and annotated image storage.
    paths : WorkspacePaths
        Workspace paths for deriving storage locations.
    """

    def __init__(
        self,
        repo: FeedbackRepository,
        store: LocalFileStore,
        paths: WorkspacePaths | None = None,
    ) -> None:
        """Initialize the feedback service.

        Parameters
        ----------
        repo : FeedbackRepository
            Repository for feedback report persistence.
        store : LocalFileStore
            File store for screenshot and annotated image storage.
        paths : WorkspacePaths, optional
            Workspace paths for deriving storage locations.
        """
        self._repo = repo
        self._store = store
        self._paths = paths

    async def submit_report(
        self,
        page_url: str,
        viewport_width: int,
        viewport_height: int,
        screenshot_data: bytes | None = None,
        annotated_data: bytes | None = None,
        annotations: list[dict[str, Any]] | None = None,
        reporter_id: str = "default",
        notes_summary: str | None = None,
        document_title: str | None = None,
        user_agent: str | None = None,
    ) -> FeedbackReport:
        """Create a new feedback report and store associated screenshot
        files and annotations.

        The report record is created first to obtain a primary key,
        then screenshot files are stored at
        ``{report_id}/screenshot.png`` and
        ``{report_id}/annotated.png`` relative to the store root.
        Finally, any annotation records are persisted.

        Parameters
        ----------
        page_url : str
            URL of the page being reviewed.
        viewport_width : int
            Browser viewport width in pixels at capture time.
        viewport_height : int
            Browser viewport height in pixels at capture time.
        screenshot_data : bytes, optional
            Raw PNG bytes of the page screenshot.
        annotated_data : bytes, optional
            Raw PNG bytes of the annotated screenshot.
        annotations : list[dict[str, Any]], optional
            List of annotation dicts, each with keys ``type``,
            ``note``, and ``data``.
        reporter_id : str, optional
            Identifier of the person who submitted the report.
            Defaults to ``"default"``.
        notes_summary : str, optional
            Optional summary text for the report.
        document_title : str, optional
            Document title at annotation time.
        user_agent : str, optional
            Browser user agent string at annotation time.

        Returns
        -------
        FeedbackReport
            The newly created feedback report with generated ``id``.
        """
        report = await self._repo.create_report(
            page_url=page_url,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            screenshot_path=None,
            annotated_path=None,
            reporter_id=reporter_id,
            notes_summary=notes_summary,
            document_title=document_title,
            user_agent=user_agent,
        )

        if screenshot_data is not None:
            path = f"{report.id}/screenshot.png"
            await self._store.put(path, _bytes_to_stream(screenshot_data))
            report.screenshot_path = path

        if annotated_data is not None:
            path = f"{report.id}/annotated.png"
            await self._store.put(path, _bytes_to_stream(annotated_data))
            report.annotated_path = path

        if annotations:
            for i, ann in enumerate(annotations):
                ann_type = ann.get("type", "element")
                ann_note = ann.get("note")
                ann_data = ann.get("data", "{}")
                if isinstance(ann_data, dict):
                    ann_data = json.dumps(ann_data)
                await self._repo.add_annotation(
                    report_id=report.id,
                    annotation_type=ann_type,
                    note=ann_note,
                    data=ann_data,
                    order=i,
                )

        return report

    async def list_reports(
        self,
        status: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[FeedbackReport], int]:
        """List feedback reports with optional status filter and
        pagination.

        Parameters
        ----------
        status : str, optional
            Optional status filter (``"open"``, ``"in_progress"``,
            ``"resolved"``). When ``None``, returns all reports.
        page : int, optional
            Page number (1-indexed). Defaults to ``1``.
        per_page : int, optional
            Number of results per page. Defaults to ``20``.

        Returns
        -------
        tuple[list[FeedbackReport], int]
            (Matching reports, total count).
        """
        return await self._repo.list_reports(
            status=status,
            page=page,
            per_page=per_page,
        )

    async def get_report(self, report_id: int) -> FeedbackReport | None:
        """Retrieve a single feedback report by ID.

        Parameters
        ----------
        report_id : int
            The report primary key.

        Returns
        -------
        FeedbackReport | None
            The matching report, or ``None`` if not found.
        """
        return await self._repo.get_report(report_id)

    async def update_status(
        self, report_id: int, new_status: str
    ) -> FeedbackReport | None:
        """Update the status of a feedback report.

        Parameters
        ----------
        report_id : int
            Primary key of the report to update.
        new_status : str
            New status value.

        Returns
        -------
        FeedbackReport | None
            The updated report, or ``None`` if not found.
        """
        return await self._repo.update_status(report_id, new_status)

    async def delete_report(self, report_id: int) -> bool:
        """Delete a feedback report and its associated files.

        Removes the screenshot files from the store, then deletes
        the database record.

        Parameters
        ----------
        report_id : int
            Primary key of the report to delete.

        Returns
        -------
        bool
            ``True`` if the report was deleted, ``False`` otherwise.
        """
        report = await self._repo.get_report(report_id)
        if report is None:
            return False

        if report.screenshot_path is not None:
            await self._store.delete(report.screenshot_path)
        if report.annotated_path is not None:
            await self._store.delete(report.annotated_path)

        return await self._repo.delete_report(report_id)

    async def batch_delete(self, report_ids: list[int]) -> int:
        """Delete multiple feedback reports and their associated files.

        Parameters
        ----------
        report_ids : list[int]
            Primary keys of the reports to delete.

        Returns
        -------
        int
            The number of reports successfully deleted.
        """
        for rid in report_ids:
            report = await self._repo.get_report(rid)
            if report is not None:
                if report.screenshot_path is not None:
                    await self._store.delete(report.screenshot_path)
                if report.annotated_path is not None:
                    await self._store.delete(report.annotated_path)
        return await self._repo.batch_delete(report_ids)

    async def export_report(self, report_id: int) -> dict[str, Any] | None:
        """Export a feedback report in a serialisable format.

        Returns all report data, annotations, and a screenshot URL
        suitable for agent consumption or external sharing.

        Parameters
        ----------
        report_id : int
            Primary key of the report to export.

        Returns
        -------
        dict[str, Any] | None
            Serialised report dict with keys ``id``, ``page_url``,
            ``viewport``, ``status``, ``reporter_id``,
            ``notes_summary``, ``screenshot_path``,
            ``annotated_path``, ``annotations``, ``created_at``,
            ``updated_at``, or ``None`` if not found.
        """
        report = await self._repo.get_report(report_id)
        if report is None:
            return None

        annotations = await self._repo.get_annotations(report_id)

        return {
            "id": report.id,
            "page_url": report.page_url,
            "viewport": {
                "width": report.viewport_width,
                "height": report.viewport_height,
            },
            "status": report.status,
            "reporter_id": report.reporter_id,
            "notes_summary": report.notes_summary,
            "screenshot_path": report.screenshot_path,
            "annotated_path": report.annotated_path,
            "annotations": [
                {
                    "id": a.id,
                    "annotation_type": a.annotation_type,
                    "note": a.note,
                    "data": a.data,
                    "order": a.order,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in annotations
            ],
            "created_at": report.created_at.isoformat() if report.created_at else None,
            "updated_at": report.updated_at.isoformat() if report.updated_at else None,
        }


async def _bytes_to_stream(data: bytes) -> AsyncIterator[bytes]:
    """Convert a bytes object to an async byte stream.

    Parameters
    ----------
    data : bytes
        The bytes to wrap in an async iterator.

    Yields
    ------
    bytes
        The input data as a single chunk.
    """
    yield data
