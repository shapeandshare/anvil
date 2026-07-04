"""Characterization tests for eval API router configuration.

Captures current route registration and decorator behaviour before
applying SonarCloud fixes (``responses`` dict and ``Annotated`` pattern).
These are purely cosmetic changes — the route paths, methods, status codes,
and runtime behaviour must remain identical.
"""

from __future__ import annotations

from anvil.api.v1.eval import router


class TestEvalRouteCharacterization:
    """Characterisation: eval routes are registered at expected paths."""

    def test_all_eval_routes_registered(self):
        """All expected routes are present on the eval router."""
        route_map = {
            (
                (r.path, next(iter(r.methods)))
                if isinstance(r.methods, set)
                else (r.path, "")
            )
            for r in router.routes
            if hasattr(r, "methods") and r.methods
        }
        # Normalize to (path, http_method)
        routes = {}
        for r in router.routes:
            if hasattr(r, "methods") and r.methods:
                for method in r.methods:
                    routes[(r.path, method)] = r

        # POST /eval/perplexity
        assert ("/eval/perplexity", "POST") in routes, "Missing POST /eval/perplexity"

        # POST /eval/fine-tuned (status_code=201)
        assert ("/eval/fine-tuned", "POST") in routes, "Missing POST /eval/fine-tuned"
        post_ft = routes[("/eval/fine-tuned", "POST")]
        assert (
            post_ft.status_code == 201
        ), f"Expected status_code=201, got {post_ft.status_code}"

        # GET /eval/fine-tuned
        assert ("/eval/fine-tuned", "GET") in routes, "Missing GET /eval/fine-tuned"

        # GET /sse/eval/{run_id}
        assert ("/sse/eval/{run_id}", "GET") in routes, "Missing GET /sse/eval/{run_id}"

        # GET /eval/fine-tuned/{run_id}
        assert (
            "/eval/fine-tuned/{run_id}",
            "GET",
        ) in routes, "Missing GET /eval/fine-tuned/{run_id}"

        # GET /eval/fine-tuned/{run_id}/samples
        assert (
            "/eval/fine-tuned/{run_id}/samples",
            "GET",
        ) in routes, "Missing GET /eval/fine-tuned/{run_id}/samples"
