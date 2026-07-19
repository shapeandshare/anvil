# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for FeedbackService — feedback report CRUD and export.

Uses mocked dependencies (repo, store) so no real DB or filesystem
code runs.  Focuses on business logic: delegation to repo, file
cleanup on delete, and export serialisation.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from anvil.db.models.feedback_report import FeedbackAnnotation, FeedbackReport
from anvil.db.repositories.feedback_repository import FeedbackRepository
from anvil.services.feedback.feedback_service import FeedbackService
from anvil.storage.local import LocalFileStore


@pytest.fixture
def mock_repo() -> MagicMock:
    """Mock FeedbackRepository with all async methods."""
    repo = MagicMock(spec=FeedbackRepository)
    repo.create_report = AsyncMock()
    repo.list_reports = AsyncMock()
    repo.get_report = AsyncMock()
    repo.update_status = AsyncMock()
    repo.delete_report = AsyncMock(return_value=True)
    repo.batch_delete = AsyncMock(return_value=2)
    repo.add_annotation = AsyncMock()
    repo.get_annotations = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_store() -> MagicMock:
    """Mock LocalFileStore with async delete and put."""
    store = MagicMock(spec=LocalFileStore)
    store.delete = AsyncMock()
    store.put = AsyncMock(return_value="etag-123")
    return store


@pytest.fixture
def service(mock_repo: MagicMock, mock_store: MagicMock) -> FeedbackService:
    """Create a FeedbackService wired to mocked dependencies."""
    return FeedbackService(repo=mock_repo, store=mock_store)


def _make_report(
    id: int = 1,
    status: str = "open",
    page_url: str = "https://example.com",
    screenshot_path: str | None = "1/screenshot.png",
    annotated_path: str | None = "1/annotated.png",
    reporter_id: str = "tester",
    notes_summary: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> FeedbackReport:
    """Helper to create a FeedbackReport instance with default values."""
    report = FeedbackReport(
        id=id,
        page_url=page_url,
        viewport_width=1920,
        viewport_height=1080,
        screenshot_path=screenshot_path,
        annotated_path=annotated_path,
        status=status,
        reporter_id=reporter_id,
        notes_summary=notes_summary,
    )
    report.created_at = created_at or datetime(2026, 7, 1, 12, 0, 0)
    report.updated_at = updated_at or datetime(2026, 7, 1, 12, 30, 0)
    return report


def _make_annotation(
    id: int = 1,
    report_id: int = 1,
    annotation_type: str = "highlight",
    note: str | None = "test note",
    data: str = '{"x": 100, "y": 200}',
    order: int = 0,
) -> FeedbackAnnotation:
    """Helper to create a FeedbackAnnotation instance."""
    annotation = FeedbackAnnotation(
        id=id,
        report_id=report_id,
        annotation_type=annotation_type,
        note=note,
        data=data,
        order=order,
    )
    annotation.created_at = datetime(2026, 7, 1, 12, 0, 0)
    return annotation


########################################################################
# T048: list_reports
########################################################################


class TestListReports:
    """Tests for FeedbackService.list_reports."""

    @pytest.mark.asyncio
    async def test_returns_paginated_results(
        self, service: FeedbackService, mock_repo: MagicMock
    ) -> None:
        """list_reports returns paginated results with total count."""
        reports = [_make_report(id=1), _make_report(id=2)]
        mock_repo.list_reports.return_value = (reports, 2)

        result, total = await service.list_reports(page=1, per_page=20)

        assert len(result) == 2
        assert total == 2
        mock_repo.list_reports.assert_called_once_with(status=None, page=1, per_page=20)

    @pytest.mark.asyncio
    async def test_filters_by_status(
        self, service: FeedbackService, mock_repo: MagicMock
    ) -> None:
        """list_reports filters by status when provided."""
        reports = [_make_report(id=1, status="open")]
        mock_repo.list_reports.return_value = (reports, 1)

        result, total = await service.list_reports(status="open")

        assert len(result) == 1
        assert total == 1
        mock_repo.list_reports.assert_called_once_with(
            status="open", page=1, per_page=20
        )

    @pytest.mark.asyncio
    async def test_empty_results(
        self, service: FeedbackService, mock_repo: MagicMock
    ) -> None:
        """list_reports returns empty list when no reports match."""
        mock_repo.list_reports.return_value = ([], 0)

        result, total = await service.list_reports(status="resolved")

        assert len(result) == 0
        assert total == 0

    @pytest.mark.asyncio
    async def test_pagination_parameters(
        self, service: FeedbackService, mock_repo: MagicMock
    ) -> None:
        """list_reports passes pagination params to the repo."""
        mock_repo.list_reports.return_value = ([], 0)

        await service.list_reports(page=2, per_page=10)

        mock_repo.list_reports.assert_called_once_with(status=None, page=2, per_page=10)


########################################################################
# T049: update_status
########################################################################


class TestUpdateStatus:
    """Tests for FeedbackService.update_status."""

    @pytest.mark.asyncio
    async def test_updates_status_successfully(
        self, service: FeedbackService, mock_repo: MagicMock
    ) -> None:
        """update_status transitions a report to a new status."""
        updated = _make_report(id=1, status="in_progress")
        mock_repo.update_status.return_value = updated

        result = await service.update_status(1, "in_progress")

        assert result is not None
        assert result.status == "in_progress"
        mock_repo.update_status.assert_called_once_with(1, "in_progress")

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(
        self, service: FeedbackService, mock_repo: MagicMock
    ) -> None:
        """update_status returns None when report does not exist."""
        mock_repo.update_status.return_value = None

        result = await service.update_status(999, "resolved")

        assert result is None

    @pytest.mark.asyncio
    async def test_transitions_open_to_in_progress(
        self, service: FeedbackService, mock_repo: MagicMock
    ) -> None:
        """Status can transition from open to in_progress."""
        updated = _make_report(id=1, status="in_progress")
        mock_repo.update_status.return_value = updated

        result = await service.update_status(1, "in_progress")

        assert result is not None
        assert result.status == "in_progress"

    @pytest.mark.asyncio
    async def test_transitions_in_progress_to_resolved(
        self, service: FeedbackService, mock_repo: MagicMock
    ) -> None:
        """Status can transition from in_progress to resolved."""
        updated = _make_report(id=1, status="resolved")
        mock_repo.update_status.return_value = updated

        result = await service.update_status(1, "resolved")

        assert result is not None
        assert result.status == "resolved"

    @pytest.mark.asyncio
    async def test_transitions_resolved_to_open(
        self, service: FeedbackService, mock_repo: MagicMock
    ) -> None:
        """Status can transition from resolved back to open."""
        updated = _make_report(id=1, status="open")
        mock_repo.update_status.return_value = updated

        result = await service.update_status(1, "open")

        assert result is not None
        assert result.status == "open"


########################################################################
# T050: delete_report
########################################################################


class TestDeleteReport:
    """Tests for FeedbackService.delete_report."""

    @pytest.mark.asyncio
    async def test_removes_screenshot_files_and_deletes_record(
        self, service: FeedbackService, mock_repo: MagicMock, mock_store: MagicMock
    ) -> None:
        """delete_report removes screenshot files from store and DB record."""
        report = _make_report(
            id=1,
            screenshot_path="1/screenshot.png",
            annotated_path="1/annotated.png",
        )
        mock_repo.get_report.return_value = report

        result = await service.delete_report(1)

        assert result is True
        mock_store.delete.assert_any_call("1/screenshot.png")
        mock_store.delete.assert_any_call("1/annotated.png")
        assert mock_store.delete.call_count == 2
        mock_repo.delete_report.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_returns_false_when_report_not_found(
        self, service: FeedbackService, mock_repo: MagicMock
    ) -> None:
        """delete_report returns False when report does not exist."""
        mock_repo.get_report.return_value = None

        result = await service.delete_report(999)

        assert result is False
        mock_repo.delete_report.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_missing_screenshot_files(
        self, service: FeedbackService, mock_repo: MagicMock, mock_store: MagicMock
    ) -> None:
        """delete_report gracefully handles missing screenshot paths."""
        report = _make_report(id=1, screenshot_path=None, annotated_path=None)
        mock_repo.get_report.return_value = report

        result = await service.delete_report(1)

        assert result is True
        mock_store.delete.assert_not_called()
        mock_repo.delete_report.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_handles_partial_screenshot_files(
        self, service: FeedbackService, mock_repo: MagicMock, mock_store: MagicMock
    ) -> None:
        """delete_report handles when only one screenshot path exists."""
        report = _make_report(
            id=1, screenshot_path="1/screenshot.png", annotated_path=None
        )
        mock_repo.get_report.return_value = report

        result = await service.delete_report(1)

        assert result is True
        mock_store.delete.assert_called_once_with("1/screenshot.png")
        mock_repo.delete_report.assert_called_once_with(1)


########################################################################
# T051: export_report
########################################################################


class TestExportReport:
    """Tests for FeedbackService.export_report."""

    @pytest.mark.asyncio
    async def test_returns_structured_dict_with_annotations(
        self, service: FeedbackService, mock_repo: MagicMock
    ) -> None:
        """export_report returns a structured dict with all metadata."""
        report = _make_report(
            id=1,
            page_url="https://example.com",
            screenshot_path="1/screenshot.png",
            annotated_path="1/annotated.png",
            notes_summary="some notes",
            reporter_id="tester",
        )
        annotations = [
            _make_annotation(
                id=1,
                annotation_type="highlight",
                note="look here",
                data='{"x": 100}',
                order=0,
            ),
            _make_annotation(
                id=2,
                annotation_type="circle",
                note="and here",
                data='{"x": 200}',
                order=1,
            ),
        ]
        mock_repo.get_report.return_value = report
        mock_repo.get_annotations.return_value = annotations

        result = await service.export_report(1)

        assert result is not None
        assert result["id"] == 1
        assert result["page_url"] == "https://example.com"
        assert result["viewport"] == {"width": 1920, "height": 1080}
        assert result["status"] == "open"
        assert result["reporter_id"] == "tester"
        assert result["notes_summary"] == "some notes"
        assert result["screenshot_path"] == "1/screenshot.png"
        assert result["annotated_path"] == "1/annotated.png"
        assert len(result["annotations"]) == 2
        assert result["annotations"][0]["annotation_type"] == "highlight"
        assert result["annotations"][0]["note"] == "look here"
        assert result["annotations"][0]["data"] == '{"x": 100}'
        assert result["annotations"][0]["order"] == 0
        assert result["annotations"][1]["annotation_type"] == "circle"
        assert result["annotations"][1]["data"] == '{"x": 200}'
        assert result["annotations"][1]["order"] == 1
        assert result["created_at"] is not None
        assert result["updated_at"] is not None

    @pytest.mark.asyncio
    async def test_returns_none_when_report_not_found(
        self, service: FeedbackService, mock_repo: MagicMock
    ) -> None:
        """export_report returns None when report does not exist."""
        mock_repo.get_report.return_value = None

        result = await service.export_report(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_empty_annotations_list(
        self, service: FeedbackService, mock_repo: MagicMock
    ) -> None:
        """export_report returns empty annotations list when none exist."""
        report = _make_report(id=1)
        mock_repo.get_report.return_value = report
        mock_repo.get_annotations.return_value = []

        result = await service.export_report(1)

        assert result is not None
        assert result["annotations"] == []

    @pytest.mark.asyncio
    async def test_formats_dates_as_iso_strings(
        self, service: FeedbackService, mock_repo: MagicMock
    ) -> None:
        """export_report formats timestamps as ISO 8601 strings."""
        created = datetime(2026, 7, 1, 12, 0, 0)
        updated = datetime(2026, 7, 2, 14, 30, 0)
        report = _make_report(id=1, created_at=created, updated_at=updated)
        mock_repo.get_report.return_value = report
        mock_repo.get_annotations.return_value = []

        result = await service.export_report(1)

        assert result is not None
        assert result["created_at"] == "2026-07-01T12:00:00"
        assert result["updated_at"] == "2026-07-02T14:30:00"


########################################################################
# T021: submit_report creates report with screenshot
########################################################################


class TestCreateReport:
    """Tests for FeedbackService.submit_report."""

    @pytest.mark.asyncio
    async def test_creates_report_with_screenshot(
        self, service: FeedbackService, mock_repo: MagicMock, mock_store: MagicMock
    ) -> None:
        """submit_report with screenshot_data stores the file and creates
        a DB record.
        """
        report = _make_report(id=1, screenshot_path="1/screenshot.png")
        mock_repo.create_report.return_value = report

        result = await service.submit_report(
            page_url="https://example.com",
            viewport_width=1024,
            viewport_height=768,
            screenshot_data=b"fake-png-bytes",
        )

        mock_repo.create_report.assert_awaited_once()
        mock_store.put.assert_awaited_once()
        assert result.id == 1
        assert result.screenshot_path == "1/screenshot.png"

    @pytest.mark.asyncio
    async def test_creates_report_without_screenshot(
        self, service: FeedbackService, mock_repo: MagicMock, mock_store: MagicMock
    ) -> None:
        """submit_report without screenshot data still creates a DB
        record but does not store any file.
        """
        report = _make_report(id=2, screenshot_path=None)
        mock_repo.create_report.return_value = report

        result = await service.submit_report(
            page_url="https://example.com",
            viewport_width=1024,
            viewport_height=768,
        )

        mock_repo.create_report.assert_awaited_once()
        mock_store.put.assert_not_called()
        assert result.id == 2
        assert result.screenshot_path is None

    @pytest.mark.asyncio
    async def test_creates_report_with_annotated_screenshot(
        self, service: FeedbackService, mock_repo: MagicMock, mock_store: MagicMock
    ) -> None:
        """submit_report with annotated screenshot stores both files."""
        report = _make_report(
            id=3,
            screenshot_path="3/screenshot.png",
            annotated_path="3/annotated.png",
        )
        mock_repo.create_report.return_value = report

        result = await service.submit_report(
            page_url="https://example.com",
            viewport_width=1024,
            viewport_height=768,
            screenshot_data=b"fake-png-bytes",
            annotated_data=b"fake-annotated-png-bytes",
        )

        assert mock_store.put.await_count == 2
        assert result.screenshot_path == "3/screenshot.png"
        assert result.annotated_path == "3/annotated.png"


########################################################################
# T022: submit with element annotation
########################################################################


class TestSubmitWithAnnotations:
    """Tests for FeedbackService.submit_report with annotations."""

    @pytest.mark.asyncio
    async def test_submit_with_element_annotation_stores_annotation(
        self, service: FeedbackService, mock_repo: MagicMock, mock_store: MagicMock
    ) -> None:
        """submit_report with element annotations stores them via
        repo.add_annotation.
        """
        report = _make_report(id=10, screenshot_path="10/screenshot.png")
        mock_repo.create_report.return_value = report

        result = await service.submit_report(
            page_url="https://example.com",
            viewport_width=1024,
            viewport_height=768,
            screenshot_data=b"fake-png-bytes",
            reporter_id="tester-1",
            notes_summary="UI bug",
            annotations=[
                {
                    "type": "element",
                    "note": "Submit button is misaligned",
                    "data": '{"selector": ".btn-submit", "x": 300, "y": 450}',
                }
            ],
        )

        assert result.id == 10
        mock_repo.add_annotation.assert_awaited_once()
        call_kwargs = mock_repo.add_annotation.call_args.kwargs
        assert call_kwargs["report_id"] == 10
        assert call_kwargs["annotation_type"] == "element"
        assert call_kwargs["order"] == 0

    @pytest.mark.asyncio
    async def test_submit_with_multiple_annotations(
        self, service: FeedbackService, mock_repo: MagicMock, mock_store: MagicMock
    ) -> None:
        """submit_report with multiple annotations stores all of them."""
        report = _make_report(id=20, screenshot_path="20/screenshot.png")
        mock_repo.create_report.return_value = report

        result = await service.submit_report(
            page_url="https://example.com",
            viewport_width=1024,
            viewport_height=768,
            screenshot_data=b"fake-png-bytes",
            reporter_id="tester-2",
            notes_summary="Two UI bugs",
            annotations=[
                {"type": "element", "note": "First issue", "data": '{"x": 100}'},
                {"type": "element", "note": "Second issue", "data": '{"x": 300}'},
            ],
        )

        assert result.id == 20
        assert mock_repo.add_annotation.await_count == 2

    @pytest.mark.asyncio
    async def test_submit_without_annotations(
        self, service: FeedbackService, mock_repo: MagicMock, mock_store: MagicMock
    ) -> None:
        """submit_report without annotations skips add_annotation."""
        report = _make_report(id=30)
        mock_repo.create_report.return_value = report

        result = await service.submit_report(
            page_url="https://example.com",
            viewport_width=1024,
            viewport_height=768,
        )

        assert result.id == 30
        mock_repo.add_annotation.assert_not_called()


########################################################################
# T037: submit with circle annotation
########################################################################


class TestSubmitWithCircleAnnotation:
    """Tests for FeedbackService.submit_report with circle annotations."""

    @pytest.mark.asyncio
    async def test_submit_with_circle_annotation_stores_center_and_radius(
        self, service: FeedbackService, mock_repo: MagicMock, mock_store: MagicMock
    ) -> None:
        """submit_report with circle annotations stores correct cx, cy, radius."""
        report = _make_report(id=40, screenshot_path="40/screenshot.png")
        mock_repo.create_report.return_value = report

        result = await service.submit_report(
            page_url="https://example.com",
            viewport_width=1024,
            viewport_height=768,
            screenshot_data=b"fake-png-bytes",
            reporter_id="tester-circle",
            notes_summary="Circle annotation test",
            annotations=[
                {
                    "type": "circle",
                    "note": "Look at this area",
                    "data": '{"cx": 300, "cy": 450, "radius": 50}',
                }
            ],
        )

        assert result.id == 40
        mock_repo.add_annotation.assert_awaited_once()
        call_kwargs = mock_repo.add_annotation.call_args.kwargs
        assert call_kwargs["report_id"] == 40
        assert call_kwargs["annotation_type"] == "circle"
        assert call_kwargs["order"] == 0

        stored_data = call_kwargs["data"]
        parsed = json.loads(stored_data)
        assert parsed["cx"] == 300
        assert parsed["cy"] == 450
        assert parsed["radius"] == 50

    @pytest.mark.asyncio
    async def test_submit_with_multiple_circle_annotations(
        self, service: FeedbackService, mock_repo: MagicMock, mock_store: MagicMock
    ) -> None:
        """submit_report with multiple circle annotations stores all."""
        report = _make_report(id=41, screenshot_path="41/screenshot.png")
        mock_repo.create_report.return_value = report

        result = await service.submit_report(
            page_url="https://example.com",
            viewport_width=1024,
            viewport_height=768,
            screenshot_data=b"fake-png-bytes",
            reporter_id="tester-circle-multi",
            annotations=[
                {
                    "type": "circle",
                    "note": "First circle",
                    "data": '{"cx": 100, "cy": 200, "radius": 30}',
                },
                {
                    "type": "circle",
                    "note": "Second circle",
                    "data": '{"cx": 500, "cy": 600, "radius": 75}',
                },
            ],
        )

        assert result.id == 41
        assert mock_repo.add_annotation.await_count == 2
        first_call = mock_repo.add_annotation.call_args_list[0].kwargs
        second_call = mock_repo.add_annotation.call_args_list[1].kwargs
        assert first_call["annotation_type"] == "circle"
        assert second_call["annotation_type"] == "circle"
        assert first_call["order"] == 0
        assert second_call["order"] == 1

    @pytest.mark.asyncio
    async def test_submit_with_circle_data_as_dict(
        self, service: FeedbackService, mock_repo: MagicMock, mock_store: MagicMock
    ) -> None:
        """submit_report accepts circle data as a dict (not string)."""
        report = _make_report(id=42, screenshot_path="42/screenshot.png")
        mock_repo.create_report.return_value = report

        result = await service.submit_report(
            page_url="https://example.com",
            viewport_width=1024,
            viewport_height=768,
            screenshot_data=b"fake-png-bytes",
            reporter_id="tester-circle-dict",
            annotations=[
                {
                    "type": "circle",
                    "note": "Circle with dict data",
                    "data": {"cx": 200, "cy": 350, "radius": 60},
                }
            ],
        )

        assert result.id == 42
        mock_repo.add_annotation.assert_awaited_once()
        stored_data = mock_repo.add_annotation.call_args.kwargs["data"]
        parsed = json.loads(stored_data)
        assert parsed["cx"] == 200
        assert parsed["radius"] == 60


########################################################################
# T038: submit with freehand annotation
########################################################################


class TestSubmitWithFreehandAnnotation:
    """Tests for FeedbackService.submit_report with freehand annotations."""

    @pytest.mark.asyncio
    async def test_submit_with_freehand_annotation_stores_path_data(
        self, service: FeedbackService, mock_repo: MagicMock, mock_store: MagicMock
    ) -> None:
        """submit_report with freehand annotations stores correct path data."""
        report = _make_report(id=50, screenshot_path="50/screenshot.png")
        mock_repo.create_report.return_value = report

        path = [[100, 200], [150, 250], [200, 300], [180, 350]]
        bounds = {"minX": 100, "minY": 200, "maxX": 200, "maxY": 350}
        result = await service.submit_report(
            page_url="https://example.com",
            viewport_width=1024,
            viewport_height=768,
            screenshot_data=b"fake-png-bytes",
            reporter_id="tester-freehand",
            notes_summary="Freehand annotation test",
            annotations=[
                {
                    "type": "freehand",
                    "note": "Freehand scribble",
                    "data": json.dumps({"path": path, "bounds": bounds}),
                }
            ],
        )

        assert result.id == 50
        mock_repo.add_annotation.assert_awaited_once()
        call_kwargs = mock_repo.add_annotation.call_args.kwargs
        assert call_kwargs["report_id"] == 50
        assert call_kwargs["annotation_type"] == "freehand"
        assert call_kwargs["order"] == 0

        stored_data = json.loads(call_kwargs["data"])
        assert stored_data["path"] == path
        assert stored_data["bounds"] == bounds

    @pytest.mark.asyncio
    async def test_submit_with_multiple_freehand_annotations(
        self, service: FeedbackService, mock_repo: MagicMock, mock_store: MagicMock
    ) -> None:
        """submit_report with multiple freehand annotations stores all."""
        report = _make_report(id=51, screenshot_path="51/screenshot.png")
        mock_repo.create_report.return_value = report

        result = await service.submit_report(
            page_url="https://example.com",
            viewport_width=1024,
            viewport_height=768,
            screenshot_data=b"fake-png-bytes",
            reporter_id="tester-freehand-multi",
            annotations=[
                {
                    "type": "freehand",
                    "note": "Path one",
                    "data": json.dumps(
                        {
                            "path": [[10, 20], [30, 40]],
                            "bounds": {"minX": 10, "minY": 20, "maxX": 30, "maxY": 40},
                        }
                    ),
                },
                {
                    "type": "freehand",
                    "note": "Path two",
                    "data": json.dumps(
                        {
                            "path": [[100, 100], [200, 200]],
                            "bounds": {
                                "minX": 100,
                                "minY": 100,
                                "maxX": 200,
                                "maxY": 200,
                            },
                        }
                    ),
                },
            ],
        )

        assert result.id == 51
        assert mock_repo.add_annotation.await_count == 2
        first_call = mock_repo.add_annotation.call_args_list[0].kwargs
        second_call = mock_repo.add_annotation.call_args_list[1].kwargs
        assert first_call["annotation_type"] == "freehand"
        assert second_call["annotation_type"] == "freehand"

    @pytest.mark.asyncio
    async def test_submit_with_mixed_annotation_types(
        self, service: FeedbackService, mock_repo: MagicMock, mock_store: MagicMock
    ) -> None:
        """submit_report with mixed element, circle, and freehand annotations."""
        report = _make_report(id=52, screenshot_path="52/screenshot.png")
        mock_repo.create_report.return_value = report

        result = await service.submit_report(
            page_url="https://example.com",
            viewport_width=1024,
            viewport_height=768,
            screenshot_data=b"fake-png-bytes",
            reporter_id="tester-mixed",
            annotations=[
                {
                    "type": "element",
                    "note": "Element annotation",
                    "data": '{"x": 100, "y": 200}',
                },
                {
                    "type": "circle",
                    "note": "Circle annotation",
                    "data": '{"cx": 300, "cy": 400, "radius": 50}',
                },
                {
                    "type": "freehand",
                    "note": "Freehand annotation",
                    "data": json.dumps(
                        {
                            "path": [[10, 10], [20, 20]],
                            "bounds": {"minX": 10, "minY": 10, "maxX": 20, "maxY": 20},
                        }
                    ),
                },
            ],
        )

        assert result.id == 52
        assert mock_repo.add_annotation.await_count == 3
        types = [
            call.kwargs["annotation_type"]
            for call in mock_repo.add_annotation.call_args_list
        ]
        assert types == ["element", "circle", "freehand"]
