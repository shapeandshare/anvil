# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for SonarCloud code smells in fine-tune dataset and chat
template API routes.

Verifies that all route handlers use ``Annotated`` for dependency injection
(S8410) and that all ``HTTPException`` raises have corresponding
``responses`` entries in the route decorator (S8415).
"""

from __future__ import annotations

import inspect

import pytest
from fastapi.routing import APIRoute

from anvil.api.v1.fine_tune_datasets import router

########################################################################
# Helpers
########################################################################


def _find_route(path: str, method: str) -> APIRoute:
    """Find a route by path and method in the fine-tune datasets router.

    Parameters
    ----------
    path : str
        URL path as defined in the router (e.g. ``/chat-templates``).
    method : str
        HTTP method (e.g. ``"POST"``).

    Returns
    -------
    APIRoute
        The matching route object.

    Raises
    ------
    AssertionError
        If no matching route is found.
    """
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path == path and method in route.methods:  # type: ignore[operator]
            return route
    raise AssertionError(
        f"Route {method} {path} not found in fine-tune datasets router"
    )


def _get_responses(route: APIRoute) -> dict:
    """Retrieve the ``responses`` dict from a route, if any.

    Parameters
    ----------
    route : APIRoute
        The FastAPI route object.

    Returns
    -------
    dict
        The responses dict, or an empty dict if not set.
    """
    if hasattr(route, "responses") and route.responses:
        return route.responses
    return {}


########################################################################
# S8410 — Annotated dependency injection
########################################################################

_ALL_ROUTES: list[tuple[str, str]] = [
    ("/chat-templates", "POST"),
    ("/chat-templates", "GET"),
    ("/fine-tune-datasets", "POST"),
    ("/fine-tune-datasets/jobs/{job_id}/status", "GET"),
    ("/fine-tune-datasets/{ftd_id}", "GET"),
    ("/fine-tune-datasets", "GET"),
    ("/fine-tune-datasets/{ftd_id}/retry", "POST"),
]


@pytest.mark.parametrize("route_path,method", _ALL_ROUTES)
def test_all_routes_use_annotated_depends(route_path: str, method: str) -> None:
    """S8410: Every route handler uses ``Annotated`` for ``workbench``."""
    route = _find_route(route_path, method)
    sig = inspect.signature(route.endpoint)
    workbench_param = sig.parameters.get("workbench")
    assert (
        workbench_param is not None
    ), f"{method} {route_path}: missing 'workbench' parameter"

    # With ``from __future__ import annotations`` the annotation is a string.
    ann = route.endpoint.__annotations__.get("workbench", "")
    assert "Annotated" in ann, (
        f"{method} {route_path}: workbench not using Annotated " f"(got {ann!r})"
    )


########################################################################
# S8415 — Documented HTTPException responses
########################################################################

# Routes that raise HTTPException and the status codes they raise.
_EXCEPTION_ROUTES: dict[tuple[str, str], set[int]] = {
    ("/chat-templates", "POST"): {409},
    ("/fine-tune-datasets", "POST"): {404, 409},
    ("/fine-tune-datasets/jobs/{job_id}/status", "GET"): {404},
    ("/fine-tune-datasets/{ftd_id}", "GET"): {404},
    ("/fine-tune-datasets/{ftd_id}/retry", "POST"): {404, 409},
}


@pytest.mark.parametrize(
    "route_path,method,expected_codes",
    [(path, method, codes) for (path, method), codes in _EXCEPTION_ROUTES.items()],
)
def test_routes_document_http_exceptions(
    route_path: str,
    method: str,
    expected_codes: set[int],
) -> None:
    """S8415: Routes raising ``HTTPException`` have documented responses."""
    route = _find_route(route_path, method)
    responses = _get_responses(route)
    documented_codes = set(responses.keys())
    missing = expected_codes - documented_codes
    assert not missing, (
        f"{method} {route_path}: missing responses entries for status "
        f"codes: {sorted(missing)}. "
        f"Documented: {sorted(documented_codes)}"
    )
