# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Repository for ``FeedbackReport`` and ``FeedbackAnnotation`` entities.

Provides CRUD operations and domain-specific queries for feedback
reports and their annotations.

Classes
-------
FeedbackRepository
    Data access for feedback reports and annotations.
"""

from __future__ import annotations

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.feedback_report import FeedbackAnnotation, FeedbackReport


class FeedbackRepository:
    """Repository for ``FeedbackReport`` and ``FeedbackAnnotation``
    entity CRUD operations.

    Supports create, read, update (status), delete, annotation
    management, and paginated listing with optional status filter.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a database session.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session used for all database operations.
        """
        self._session = session

    async def create_report(
        self,
        page_url: str,
        viewport_width: int,
        viewport_height: int,
        screenshot_path: str | None = None,
        annotated_path: str | None = None,
        reporter_id: str = "default",
        notes_summary: str | None = None,
        document_title: str | None = None,
        user_agent: str | None = None,
    ) -> FeedbackReport:
        """Persist a new feedback report and flush to generate its
        primary key.

        Parameters
        ----------
        page_url : str
            URL of the page being reviewed.
        viewport_width : int
            Browser viewport width in pixels at capture time.
        viewport_height : int
            Browser viewport height in pixels at capture time.
        screenshot_path : str, optional
            Path to the raw screenshot file.
        annotated_path : str, optional
            Path to the annotated screenshot file.
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
            The persisted instance with a generated ``id``.
        """
        report = FeedbackReport(
            page_url=page_url,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            screenshot_path=screenshot_path,
            annotated_path=annotated_path,
            reporter_id=reporter_id,
            notes_summary=notes_summary,
            document_title=document_title,
            user_agent=user_agent,
        )
        self._session.add(report)
        await self._session.flush()
        await self._session.refresh(report)
        return report

    async def get_report(self, report_id: int) -> FeedbackReport | None:
        """Retrieve a feedback report by its primary key.

        Eagerly loads the ``annotations`` relationship.

        Parameters
        ----------
        report_id : int
            Primary key of the ``FeedbackReport`` to retrieve.

        Returns
        -------
        FeedbackReport | None
            The matching ``FeedbackReport`` instance, or ``None`` if
            no record exists with the given ``report_id``.
        """
        result = await self._session.execute(
            select(FeedbackReport)
            .where(FeedbackReport.id == report_id)
            .options(selectinload(FeedbackReport.annotations))
        )
        return result.scalar_one_or_none()

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
        status : str or None
            Optional status filter (``"open"``, ``"in_progress"``,
            ``"resolved"``). When ``None``, returns all reports.
        page : int
            Page number (1-indexed). Defaults to ``1``.
        per_page : int
            Number of results per page. Defaults to ``20``.

        Returns
        -------
        tuple[list[FeedbackReport], int]
            A tuple of (matching reports ordered by creation date
            descending, total count matching the filter).
        """
        base_query = select(FeedbackReport)
        count_query = select(func.count()).select_from(FeedbackReport)

        if status is not None:
            base_query = base_query.where(FeedbackReport.status == status)
            count_query = count_query.where(FeedbackReport.status == status)

        # Total count
        count_result = await self._session.execute(count_query)
        total = count_result.scalar_one()

        # Paginated results
        offset = (page - 1) * per_page
        result = await self._session.execute(
            base_query.order_by(FeedbackReport.created_at.desc())
            .offset(offset)
            .limit(per_page)
            .options(selectinload(FeedbackReport.annotations))
        )
        items = list(result.scalars().all())

        return items, total

    async def update_status(
        self, report_id: int, new_status: str
    ) -> FeedbackReport | None:
        """Update the status of a feedback report.

        Parameters
        ----------
        report_id : int
            Primary key of the report to update.
        new_status : str
            New status value (must be a ``FeedbackStatus`` value).

        Returns
        -------
        FeedbackReport | None
            The updated report, or ``None`` if no report with the
            given ``report_id`` exists.
        """
        await self._session.execute(
            update(FeedbackReport)
            .where(FeedbackReport.id == report_id)
            .values(status=new_status)
        )
        await self._session.flush()
        return await self.get_report(report_id)

    async def delete_report(self, report_id: int) -> bool:
        """Delete a feedback report and its cascaded annotations.

        Parameters
        ----------
        report_id : int
            Primary key of the report to delete.

        Returns
        -------
        bool
            ``True`` if a row was deleted, ``False`` if no report
            existed with the given ``report_id``.
        """
        result = await self._session.execute(
            delete(FeedbackReport).where(FeedbackReport.id == report_id)
        )
        await self._session.flush()
        return result.rowcount > 0  # type: ignore[attr-defined, no-any-return]

    async def batch_delete(self, report_ids: list[int]) -> int:
        """Delete multiple feedback reports by primary key.

        Parameters
        ----------
        report_ids : list[int]
            Primary keys of the reports to delete.

        Returns
        -------
        int
            The number of reports successfully deleted.
        """
        result = await self._session.execute(
            delete(FeedbackReport).where(FeedbackReport.id.in_(report_ids))
        )
        await self._session.flush()
        return result.rowcount  # type: ignore[attr-defined, no-any-return]

    async def add_annotation(
        self,
        report_id: int,
        annotation_type: str,
        note: str | None = None,
        data: str = "{}",
        order: int = 0,
    ) -> FeedbackAnnotation:
        """Persist a new annotation and flush to generate its
        primary key.

        Parameters
        ----------
        report_id : int
            Foreign key to the ``FeedbackReport``.
        annotation_type : str
            Type of annotation (e.g. ``"highlight"``, ``"circle"``,
            ``"freehand"``).
        note : str, optional
            Optional human-readable note.
        data : str, optional
            JSON blob containing the annotation geometry and payload.
            Defaults to ``"{}"``.
        order : int, optional
            Display ordering within the report. Defaults to ``0``.

        Returns
        -------
        FeedbackAnnotation
            The persisted instance with a generated ``id``.
        """
        annotation = FeedbackAnnotation(
            report_id=report_id,
            annotation_type=annotation_type,
            note=note,
            data=data,
            order=order,
        )
        self._session.add(annotation)
        await self._session.flush()
        await self._session.refresh(annotation)
        return annotation

    async def get_annotations(self, report_id: int) -> list[FeedbackAnnotation]:
        """Retrieve all annotations for a feedback report.

        Parameters
        ----------
        report_id : int
            Primary key of the report whose annotations to fetch.

        Returns
        -------
        list[FeedbackAnnotation]
            All annotations belonging to the report, ordered by
            display order.
        """
        result = await self._session.execute(
            select(FeedbackAnnotation)
            .where(FeedbackAnnotation.report_id == report_id)
            .order_by(FeedbackAnnotation.order)
        )
        return list(result.scalars().all())
