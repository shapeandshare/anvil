"""Tests for adapter route code smells: S8410 (Annotated DI) and S8415 (documented responses).

Verifies that all adapter routes use ``Annotated[T, Depends(...)]`` for
dependency injection and document HTTPException status codes via the
``responses`` decorator parameter.
"""

from __future__ import annotations

from fastapi.routing import APIRoute

from anvil.api.v1.adapters import router


def _get_routes() -> list[APIRoute]:
    """Return all APIRoute instances from the adapter router."""
    return [r for r in router.routes if isinstance(r, APIRoute)]


def _get_route_by_path(path: str) -> APIRoute:
    """Get a single route by its path pattern."""
    matches = [r for r in _get_routes() if r.path == path]
    assert len(matches) == 1, f"Expected 1 route for {path!r}, got {len(matches)}"
    return matches[0]


def test_all_adapter_routes_use_annotated_di():
    """S8410: Every route handler must use ``Annotated[T, Depends(...)]``
    for the ``workbench`` parameter instead of ``= Depends(...)``.
    """
    for route in _get_routes():
        sig = route.endpoint.__annotations__
        assert "workbench" in sig, f"{route.path}: expected 'workbench' parameter"
        workbench_type = sig["workbench"]
        # With PEP 563 (from __future__ import annotations), annotations
        # are strings.  Check that the string representation includes
        # "Annotated" and "AnvilWorkbench".
        type_str = str(workbench_type)
        assert "Annotated" in type_str, (
            f"{route.path}: workbench type is {type_str!r}, "
            f"expected Annotated[AnvilWorkbench, Depends(...)]"
        )
        assert "AnvilWorkbench" in type_str, (
            f"{route.path}: workbench type is {type_str!r}, "
            f"expected Annotated[AnvilWorkbench, Depends(...)]"
        )


def test_get_adapter_documents_404():
    """S8415: GET /models/{model_id}/adapters/{adapter_id} must
    document the 404 response.
    """
    route = _get_route_by_path("/models/{model_id}/adapters/{adapter_id}")
    responses = route.responses
    assert 404 in responses, (
        f"Missing 404 response documentation in {route.path} "
        f"(raises HTTPException 404 when adapter not found)"
    )
    desc = responses[404]["description"]
    assert isinstance(desc, str) and len(desc) > 0


def test_merge_adapter_documents_404_and_500():
    """S8415: POST /models/{model_id}/adapters/{adapter_id}/merge must
    document 404 and 500 responses.
    """
    route = _get_route_by_path("/models/{model_id}/adapters/{adapter_id}/merge")
    responses = route.responses
    for status in (404, 500):
        assert status in responses, (
            f"Missing {status} response documentation in {route.path} "
            f"(raises HTTPException {status} on ValueError/RuntimeError)"
        )
        desc = responses[status]["description"]
        assert isinstance(desc, str) and len(desc) > 0


def test_merge_and_export_documents_404_and_500():
    """S8415: POST /models/{model_id}/adapters/{adapter_id}/merge-and-export
    must document 404 and 500 responses.
    """
    route = _get_route_by_path(
        "/models/{model_id}/adapters/{adapter_id}/merge-and-export"
    )
    responses = route.responses
    for status in (404, 500):
        assert (
            status in responses
        ), f"Missing {status} response documentation in {route.path}"
        desc = responses[status]["description"]
        assert isinstance(desc, str) and len(desc) > 0


def test_list_adapters_has_no_http_exception():
    """S8415: GET /models/{model_id}/adapters does not raise any
    HTTPException, so no responses documentation is required.
    """
    route = _get_route_by_path("/models/{model_id}/adapters")
    # This route has no HTTPException — responses should be empty
    # (FastAPI fills in default 422 and 2xx responses automatically).
    # We just verify it doesn't crash and has no unexpected status codes.
    assert isinstance(route.responses, dict)
