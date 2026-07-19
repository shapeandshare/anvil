# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the visual feedback annotation API (feature 001).

Covers the admin dashboard backend endpoints for listing, updating,
deleting, and exporting feedback reports.  Uses the ``client``
fixture (httpx.AsyncClient with in-memory SQLite).
"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.asyncio


async def _create_report(client, page_url: str = "https://example.com") -> dict:
    """Helper to create a feedback report via POST /v1/feedback."""
    r = await client.post(
        "/v1/feedback",
        data={
            "page_url": page_url,
            "viewport_width": "1920",
            "viewport_height": "1080",
            "reporter_id": "e2e-tester",
            "notes_summary": "test report",
        },
    )
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    return r.json()


########################################################################
# T052: GET /v1/feedback — paginated list with status filter
########################################################################


class TestListFeedback:
    """E2E tests for GET /v1/feedback."""

    async def test_returns_paginated_list(self, client) -> None:
        """GET /v1/feedback returns paginated list of reports."""
        await _create_report(client)
        await _create_report(client, "https://example.org")

        r = await client.get("/v1/feedback")
        assert r.status_code == 200

        data = r.json()
        assert data["ok"] is True
        assert "reports" in data
        assert "total" in data
        assert data["total"] >= 2
        assert len(data["reports"]) >= 2

    async def test_filters_by_status(self, client) -> None:
        """GET /v1/feedback?status=open returns only open reports."""
        await _create_report(client)

        r = await client.get("/v1/feedback", params={"status": "open"})
        assert r.status_code == 200

        data = r.json()
        assert data["ok"] is True
        for report in data["reports"]:
            assert report["status"] == "open"

    async def test_empty_results_for_unknown_status(self, client) -> None:
        """GET /v1/feedback?status=resolved returns empty when none."""
        await _create_report(client)

        r = await client.get("/v1/feedback", params={"status": "resolved"})
        assert r.status_code == 200

        data = r.json()
        assert data["total"] == 0
        assert data["reports"] == []

    async def test_pagination_parameters(self, client) -> None:
        """GET /v1/feedback respects page and per_page params."""
        for i in range(3):
            await _create_report(client, f"https://example{i}.com")

        r = await client.get("/v1/feedback", params={"page": 1, "per_page": 2})
        assert r.status_code == 200

        data = r.json()
        assert len(data["reports"]) == 2
        assert data["total"] >= 3

    async def test_report_has_expected_fields(self, client) -> None:
        """Each report in the list has the expected shape."""
        await _create_report(client)

        r = await client.get("/v1/feedback")
        data = r.json()
        report = data["reports"][0]

        assert "id" in report
        assert "page_url" in report
        assert "status" in report
        assert "reporter_id" in report
        assert "created_at" in report
        assert "updated_at" in report
        assert "viewport_width" in report
        assert "viewport_height" in report
        assert "annotation_count" in report


########################################################################
# T053: PATCH /v1/feedback/{id}/status — update report status
########################################################################


class TestUpdateStatus:
    """E2E tests for PATCH /v1/feedback/{id}/status."""

    async def test_updates_status(self, client) -> None:
        """PATCH /v1/feedback/{id}/status transitions report status."""
        created = await _create_report(client)
        report_id = created["id"]

        r = await client.patch(
            f"/v1/feedback/{report_id}/status",
            json={"status": "in_progress"},
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True

        r = await client.get(f"/v1/feedback/{report_id}")
        assert r.status_code == 200
        assert r.json()["report"]["status"] == "in_progress"

    async def test_returns_404_for_nonexistent_report(self, client) -> None:
        """PATCH returns 404 when report does not exist."""
        r = await client.patch(
            "/v1/feedback/99999/status",
            json={"status": "resolved"},
        )
        assert r.status_code == 404

    async def test_returns_400_when_status_missing(self, client) -> None:
        """PATCH returns 400 when status field is missing."""
        await _create_report(client)

        r = await client.patch(
            "/v1/feedback/1/status",
            json={},
        )
        assert r.status_code == 400

    async def test_transitions_through_all_statuses(self, client) -> None:
        """Status can cycle through open -> in_progress -> resolved."""
        created = await _create_report(client)
        report_id = created["id"]

        r = await client.patch(
            f"/v1/feedback/{report_id}/status",
            json={"status": "in_progress"},
        )
        assert r.status_code == 200

        r = await client.patch(
            f"/v1/feedback/{report_id}/status",
            json={"status": "resolved"},
        )
        assert r.status_code == 200

        r = await client.get(f"/v1/feedback/{report_id}")
        assert r.json()["report"]["status"] == "resolved"


########################################################################
# T054: DELETE /v1/feedback/{id} — remove report
########################################################################


class TestDeleteReport:
    """E2E tests for DELETE /v1/feedback/{id}."""

    async def test_deletes_report(self, client) -> None:
        """DELETE /v1/feedback/{id} removes the report."""
        created = await _create_report(client)
        report_id = created["id"]

        r = await client.delete(f"/v1/feedback/{report_id}")
        assert r.status_code == 200
        assert r.json()["ok"] is True

        r = await client.get(f"/v1/feedback/{report_id}")
        assert r.status_code == 404

    async def test_returns_404_for_nonexistent_report(self, client) -> None:
        """DELETE returns 404 when report does not exist."""
        r = await client.delete("/v1/feedback/99999")
        assert r.status_code == 404


########################################################################
# T055: GET /v1/feedback/{id}/export — machine-readable JSON
########################################################################


class TestExportReport:
    """E2E tests for GET /v1/feedback/{id}/export."""

    async def test_returns_machine_readable_json(self, client) -> None:
        """GET /v1/feedback/{id}/export returns structured JSON export."""
        created = await _create_report(client)
        report_id = created["id"]

        r = await client.get(f"/v1/feedback/{report_id}/export")
        assert r.status_code == 200

        data = r.json()
        assert data["ok"] is True
        export = data["export"]

        assert export["id"] == report_id
        assert export["page_url"] == "https://example.com"
        assert export["viewport"] == {"width": 1920, "height": 1080}
        assert export["status"] == "open"
        assert export["reporter_id"] == "e2e-tester"
        assert export["notes_summary"] == "test report"
        assert "screenshot_path" in export
        assert "annotated_path" in export
        assert isinstance(export["annotations"], list)
        assert "created_at" in export
        assert "updated_at" in export

    async def test_returns_404_for_nonexistent_report(self, client) -> None:
        """GET /v1/feedback/{id}/export returns 404 when not found."""
        r = await client.get("/v1/feedback/99999/export")
        assert r.status_code == 404


########################################################################
# Batch delete and screenshot endpoint
########################################################################


class TestBatchDelete:
    """E2E tests for POST /v1/feedback/batch-delete."""

    async def test_deletes_multiple_reports(self, client) -> None:
        """POST /v1/feedback/batch-delete removes multiple reports."""
        r1 = await _create_report(client, "https://a.com")
        r2 = await _create_report(client, "https://b.com")
        r3 = await _create_report(client, "https://c.com")

        r = await client.post(
            "/v1/feedback/batch-delete",
            json={"ids": [r1["id"], r3["id"]]},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["deleted"] == 2

        r = await client.get(f"/v1/feedback/{r1['id']}")
        assert r.status_code == 404
        r = await client.get(f"/v1/feedback/{r2['id']}")
        assert r.status_code == 200
        r = await client.get(f"/v1/feedback/{r3['id']}")
        assert r.status_code == 404

    async def test_returns_400_for_missing_ids_field(self, client) -> None:
        """POST /v1/feedback/batch-delete returns 400 without ids."""
        r = await client.post(
            "/v1/feedback/batch-delete",
            json={},
        )
        assert r.status_code == 400

    async def test_returns_400_for_empty_ids_list(self, client) -> None:
        """POST /v1/feedback/batch-delete returns 400 for empty list."""
        r = await client.post(
            "/v1/feedback/batch-delete",
            json={"ids": []},
        )
        assert r.status_code == 400


class TestGetReport:
    """E2E tests for GET /v1/feedback/{id}."""

    async def test_returns_full_report(self, client) -> None:
        """GET /v1/feedback/{id} returns full report details."""
        created = await _create_report(client)
        report_id = created["id"]

        r = await client.get(f"/v1/feedback/{report_id}")
        assert r.status_code == 200

        data = r.json()
        assert data["ok"] is True
        report = data["report"]
        assert report["id"] == report_id
        assert report["page_url"] == "https://example.com"
        assert report["status"] == "open"
        assert report["viewport_width"] == 1920
        assert report["viewport_height"] == 1080
        assert report["reporter_id"] == "e2e-tester"
        assert report["notes_summary"] == "test report"
        assert isinstance(report["annotations"], list)

    async def test_returns_404_for_nonexistent_report(self, client) -> None:
        """GET /v1/feedback/{id} returns 404 when not found."""
        r = await client.get("/v1/feedback/99999")
        assert r.status_code == 404


########################################################################
# T023: POST /v1/feedback with element annotation (multipart)
########################################################################


class TestCreateFeedbackWithAnnotations:
    """E2E tests for POST /v1/feedback with multipart annotations."""

    async def test_creates_report_with_element_annotation(self, client) -> None:
        """POST /v1/feedback with element annotation multipart form data
        returns 201.
        """
        annotations = json.dumps(
            [
                {
                    "type": "element",
                    "note": "Broken button",
                    "data": '{"selector": ".btn-primary", "x": 100, "y": 200}',
                }
            ]
        )
        r = await client.post(
            "/v1/feedback",
            data={
                "page_url": "https://example.com",
                "viewport_width": "1920",
                "viewport_height": "1080",
                "reporter_id": "e2e-tester",
                "notes_summary": "test with annotations",
                "annotations": annotations,
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["ok"] is True
        assert "id" in data

    async def test_creates_report_with_multiple_annotations(self, client) -> None:
        """POST /v1/feedback with multiple annotations stores all of them."""
        annotations = json.dumps(
            [
                {"type": "element", "note": "Issue 1", "data": '{"x": 100}'},
                {"type": "element", "note": "Issue 2", "data": '{"x": 300}'},
            ]
        )
        r = await client.post(
            "/v1/feedback",
            data={
                "page_url": "https://example.com/multi",
                "viewport_width": "1920",
                "viewport_height": "1080",
                "reporter_id": "e2e-tester",
                "notes_summary": "multiple annotations",
                "annotations": annotations,
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["ok"] is True

    async def test_creates_report_without_annotations(self, client) -> None:
        """POST /v1/feedback without annotations still works."""
        r = await client.post(
            "/v1/feedback",
            data={
                "page_url": "https://example.com/no-ann",
                "viewport_width": "1920",
                "viewport_height": "1080",
                "reporter_id": "e2e-tester",
                "notes_summary": "no annotations",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["ok"] is True


########################################################################
# T024: GET /v1/feedback/{id} returns report with annotations
########################################################################


class TestGetReportWithAnnotations:
    """E2E tests for GET /v1/feedback/{id} with annotations."""

    async def test_returns_report_with_annotations(self, client) -> None:
        """GET /v1/feedback/{id} returns the submitted report with
        annotations.
        """
        annotations = json.dumps(
            [
                {
                    "type": "element",
                    "note": "Submit button is misaligned",
                    "data": '{"selector": ".btn-submit", "x": 300, "y": 450}',
                }
            ]
        )
        created = await client.post(
            "/v1/feedback",
            data={
                "page_url": "https://example.com",
                "viewport_width": "1920",
                "viewport_height": "1080",
                "reporter_id": "e2e-tester",
                "notes_summary": "test with annotations",
                "annotations": annotations,
            },
        )
        assert created.status_code == 201
        report_id = created.json()["id"]

        r = await client.get(f"/v1/feedback/{report_id}")
        assert r.status_code == 200

        data = r.json()
        assert data["ok"] is True
        report = data["report"]
        assert report["id"] == report_id
        assert report["page_url"] == "https://example.com"
        assert report["status"] == "open"
        assert isinstance(report["annotations"], list)
        assert len(report["annotations"]) == 1
        ann = report["annotations"][0]
        assert ann["annotation_type"] == "element"
        assert ann["note"] == "Submit button is misaligned"

    async def test_returns_404_for_nonexistent_report(self, client) -> None:
        """GET /v1/feedback/{id} returns 404 when not found."""
        r = await client.get("/v1/feedback/99999")
        assert r.status_code == 404


class TestCreateFeedbackWithCircleFreehandAnnotations:
    """E2E tests for POST /v1/feedback with circle and freehand
    annotations.
    """

    async def test_creates_report_with_circle_annotation(self, client) -> None:
        """POST /v1/feedback with circle annotation stores cx, cy, radius."""
        annotations = json.dumps(
            [
                {
                    "type": "circle",
                    "note": "Circle around the button",
                    "data": '{"cx": 300, "cy": 450, "radius": 50}',
                }
            ]
        )
        r = await client.post(
            "/v1/feedback",
            data={
                "page_url": "https://example.com",
                "viewport_width": "1920",
                "viewport_height": "1080",
                "reporter_id": "e2e-tester",
                "notes_summary": "circle annotation test",
                "annotations": annotations,
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["ok"] is True
        assert "id" in data

        # Verify the annotation was stored correctly
        report_id = data["id"]
        r = await client.get(f"/v1/feedback/{report_id}")
        assert r.status_code == 200
        report_data = r.json()
        annotations = report_data["report"]["annotations"]
        assert len(annotations) == 1
        ann = annotations[0]
        assert ann["annotation_type"] == "circle"
        assert ann["note"] == "Circle around the button"
        import json as _json

        parsed = _json.loads(ann["data"])
        assert parsed["cx"] == 300
        assert parsed["cy"] == 450
        assert parsed["radius"] == 50

    async def test_creates_report_with_freehand_annotation(self, client) -> None:
        """POST /v1/feedback with freehand annotation stores path data."""
        path = [[100, 200], [150, 250], [200, 300]]
        bounds = {"minX": 100, "minY": 200, "maxX": 200, "maxY": 300}
        annotations = json.dumps(
            [
                {
                    "type": "freehand",
                    "note": "Freehand circle scribble",
                    "data": json.dumps({"path": path, "bounds": bounds}),
                }
            ]
        )
        r = await client.post(
            "/v1/feedback",
            data={
                "page_url": "https://example.com/freehand",
                "viewport_width": "1920",
                "viewport_height": "1080",
                "reporter_id": "e2e-tester",
                "notes_summary": "freehand annotation test",
                "annotations": annotations,
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["ok"] is True
        assert "id" in data

        report_id = data["id"]
        r = await client.get(f"/v1/feedback/{report_id}")
        assert r.status_code == 200
        report_data = r.json()
        annotations = report_data["report"]["annotations"]
        assert len(annotations) == 1
        ann = annotations[0]
        assert ann["annotation_type"] == "freehand"
        assert ann["note"] == "Freehand circle scribble"
        import json as _json

        parsed = _json.loads(ann["data"])
        assert parsed["path"] == path
        assert parsed["bounds"] == bounds

    async def test_creates_report_with_mixed_annotation_types(self, client) -> None:
        """POST /v1/feedback with element, circle, and freehand annotations."""
        annotations = json.dumps(
            [
                {
                    "type": "element",
                    "note": "Element issue",
                    "data": '{"x": 100, "y": 200}',
                },
                {
                    "type": "circle",
                    "note": "Circle issue",
                    "data": '{"cx": 400, "cy": 500, "radius": 75}',
                },
                {
                    "type": "freehand",
                    "note": "Freehand issue",
                    "data": json.dumps(
                        {
                            "path": [[10, 10], [20, 20]],
                            "bounds": {"minX": 10, "minY": 10, "maxX": 20, "maxY": 20},
                        }
                    ),
                },
            ]
        )
        r = await client.post(
            "/v1/feedback",
            data={
                "page_url": "https://example.com/mixed",
                "viewport_width": "1920",
                "viewport_height": "1080",
                "reporter_id": "e2e-tester",
                "notes_summary": "mixed annotation types test",
                "annotations": annotations,
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["ok"] is True
        assert "id" in data

        report_id = data["id"]
        r = await client.get(f"/v1/feedback/{report_id}")
        assert r.status_code == 200
        report_data = r.json()
        annotations = report_data["report"]["annotations"]
        assert len(annotations) == 3
        types = [a["annotation_type"] for a in annotations]
        assert "element" in types
        assert "circle" in types
        assert "freehand" in types


########################################################################
# Validation error tests for coverage
########################################################################


class TestCreateFeedbackValidationErrors:
    """E2E tests for validation error paths in POST /v1/feedback."""

    async def test_rejects_note_over_2000_chars(self, client) -> None:
        """POST /v1/feedback with note > 2000 chars returns 400."""
        annotations = json.dumps(
            [{"type": "element", "note": "x" * 2001, "data": "{}"}]
        )
        r = await client.post(
            "/v1/feedback",
            data={
                "page_url": "/test",
                "viewport_width": "1920",
                "viewport_height": "1080",
                "annotations": annotations,
            },
        )
        assert r.status_code == 400

    async def test_rejects_circle_missing_fields(self, client) -> None:
        """POST /v1/feedback with circle missing cx/cy/radius returns 400."""
        annotations = json.dumps(
            [{"type": "circle", "note": "bad", "data": "{}"}]
        )
        r = await client.post(
            "/v1/feedback",
            data={
                "page_url": "/test",
                "viewport_width": "1920",
                "viewport_height": "1080",
                "annotations": annotations,
            },
        )
        assert r.status_code == 400

    async def test_rejects_circle_negative_radius(self, client) -> None:
        """POST /v1/feedback with circle radius <= 0 returns 400."""
        data = json.dumps({"cx": 100, "cy": 100, "radius": 0})
        annotations = json.dumps(
            [{"type": "circle", "note": "bad radius", "data": data}]
        )
        r = await client.post(
            "/v1/feedback",
            data={
                "page_url": "/test",
                "viewport_width": "1920",
                "viewport_height": "1080",
                "annotations": annotations,
            },
        )
        assert r.status_code == 400

    async def test_rejects_freehand_missing_path(self, client) -> None:
        """POST /v1/feedback with freehand missing path returns 400."""
        data = json.dumps({"bounds": {"minX": 0, "minY": 0, "maxX": 10, "maxY": 10}})
        annotations = json.dumps(
            [{"type": "freehand", "note": "bad", "data": data}]
        )
        r = await client.post(
            "/v1/feedback",
            data={
                "page_url": "/test",
                "viewport_width": "1920",
                "viewport_height": "1080",
                "annotations": annotations,
            },
        )
        assert r.status_code == 400

    async def test_rejects_freehand_short_path(self, client) -> None:
        """POST /v1/feedback with freehand path < 2 points returns 400."""
        data = json.dumps(
            {"path": [[10, 10]], "bounds": {"minX": 10, "minY": 10, "maxX": 10, "maxY": 10}}
        )
        annotations = json.dumps(
            [{"type": "freehand", "note": "too short", "data": data}]
        )
        r = await client.post(
            "/v1/feedback",
            data={
                "page_url": "/test",
                "viewport_width": "1920",
                "viewport_height": "1080",
                "annotations": annotations,
            },
        )
        assert r.status_code == 400

    async def test_rejects_invalid_annotations_json(self, client) -> None:
        """POST /v1/feedback with invalid annotations JSON defaults to
        empty list (request still succeeds).
        """
        r = await client.post(
            "/v1/feedback",
            data={
                "page_url": "/test",
                "viewport_width": "1920",
                "viewport_height": "1080",
                "annotations": "not valid json",
            },
        )
        # Invalid JSON defaults to empty annotations list, not a 400
        assert r.status_code == 201
        data = r.json()
        assert data["ok"] is True


class TestScreenshot:
    """E2E tests for GET /v1/feedback/{id}/screenshot."""

    async def test_returns_404_when_no_screenshot(self, client) -> None:
        """GET /v1/feedback/{id}/screenshot returns 404 when no file."""
        created = await _create_report(client)
        report_id = created["id"]

        r = await client.get(f"/v1/feedback/{report_id}/screenshot")
        assert r.status_code == 404
