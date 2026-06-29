"""Tests for learning content routes.

Covers all Jinja2-rendered lesson pages (``/v1/learn/{page}``),
the learning index, FAQ, glossary, and utility functions exported
by the learning module. The learning router has 30 registered routes
across 5 template archetypes.
"""

from __future__ import annotations

import pytest

import anvil.api.v1.learning as learning_mod

####################################################################
# Helper: known page groups
####################################################################

# Every valid learn page (keyed by the path suffix).
# Each entry: (path_suffix, expected_template, known_text_fragment)
# known_text_fragment is a short string that MUST appear in the
# rendered HTML — sourced from the step data in learning.py.
LEARN_PAGES: list[tuple[str, str, str]] = [
    # Index page
    ("/v1/learn", "learn-index", "Data Fundamentals"),
    # Concept pages (archetypes/concept.html)
    ("/v1/learn/tokenization", "concept", "What is a Token"),
    ("/v1/learn/embeddings", "concept", "What is an Embedding"),
    ("/v1/learn/attention", "concept", "What is Attention"),
    ("/v1/learn/sampling", "concept", "From Logits to Probabilities"),
    ("/v1/learn/training-loop", "concept", "What is Training"),
    ("/v1/learn/autograd", "concept", "What is Autograd"),
    ("/v1/learn/loss", "concept", "What is Loss"),
    ("/v1/learn/parameters", "concept", "Where Parameters Live"),
    ("/v1/learn/adam", "concept", "What is Adam"),
    ("/v1/learn/export", "concept", "Why Export"),
    ("/v1/learn/fine-tuning-intro", "concept", "What Is Fine-Tuning"),
    ("/v1/learn/warmstart-vs-lora", "concept", "Full Fine-Tuning"),
    ("/v1/learn/finetune-vs-prompt-vs-rag", "concept", "When to Fine-Tune"),
    ("/v1/learn/chunking", "concept", "Why Chunk at All"),
    ("/v1/learn/content-versioning", "concept", "Why Version Your Data"),
    ("/v1/learn/experiment-tracking", "concept", "What is an Experiment Run"),
    ("/v1/learn/governance", "concept", "Why Data Governance"),
    ("/v1/learn/memory-divergence", "concept", "Knowing Before You Train"),
    ("/v1/learn/runtime-config", "concept", "What is Runtime Configuration"),
    ("/v1/learn/cloud-compute", "concept", "Why Cloud Compute"),
    ("/v1/learn/backup", "concept", "What is a Backup"),
    # Data fundamentals (archetypes/data-fundamentals.html)
    ("/v1/learn/data-fundamentals", "data-fundamentals", "Two Ways to Source Data"),
    # Architecture (archetypes/architecture.html)
    ("/v1/learn/architecture", "architecture", "The Big Picture"),
    # FAQ (archetypes/faq.html)
    ("/v1/learn/faq", "faq", "Frequently Asked Questions"),
    # Glossary (archetypes/glossary.html)
    ("/v1/learn/glossary", "glossary", "Autograd"),
]

# Non-existent learn page — must 404
INVALID_PAGE = "/v1/learn/nonexistent"


####################################################################
# Valid page tests
####################################################################


class TestLearnPages:
    """Suite of tests for all valid learn page routes."""

    @pytest.mark.parametrize("path,_template,_text", LEARN_PAGES)
    @pytest.mark.asyncio
    async def test_valid_page_returns_200(
        self, client, path: str, _template: str, _text: str
    ) -> None:
        """Every known learn page returns HTTP 200 with ``text/html``."""
        r = await client.get(path)
        assert r.status_code == 200, f"{path} expected 200, got {r.status_code}"
        assert "text/html" in r.headers.get(
            "content-type", ""
        ), f"{path} expected text/html content type"

    @pytest.mark.parametrize("path,_template,_text", LEARN_PAGES)
    @pytest.mark.asyncio
    async def test_page_content_includes_expected_text(
        self, client, path: str, _template: str, _text: str
    ) -> None:
        """Each page's HTML body contains the expected content fragment."""
        r = await client.get(path)
        assert r.status_code == 200
        assert _text in r.text, f"Expected text {_text!r} not found in {path} response"

    @pytest.mark.parametrize("path,_template,_text", LEARN_PAGES)
    @pytest.mark.asyncio
    async def test_page_content_has_html_structure(
        self, client, path: str, _template: str, _text: str
    ) -> None:
        """Each page returns well-formed HTML structure (doctype, html tag)."""
        r = await client.get(path)
        assert r.status_code == 200
        assert (
            "<!DOCTYPE html>" in r.text or "<!doctype html>" in r.text
        ), f"{path} missing DOCTYPE"
        assert "<html" in r.text, f"{path} missing <html> tag"
        assert "</html>" in r.text, f"{path} missing </html> tag"


####################################################################
# Invalid page test
####################################################################


class TestInvalidLearnPage:
    """Tests for non-existent learn pages returning 404."""

    @pytest.mark.asyncio
    async def test_invalid_page_returns_404(self, client) -> None:
        """A non-existent learn page returns HTTP 404."""
        r = await client.get(INVALID_PAGE)
        assert (
            r.status_code == 404
        ), f"Expected 404 for {INVALID_PAGE}, got {r.status_code}"

    @pytest.mark.asyncio
    async def test_invalid_page_detail(self, client) -> None:
        """A non-existent learn page returns a 404 with detail."""
        r = await client.get(INVALID_PAGE)
        assert r.status_code == 404
        body = r.json()
        assert "detail" in body


####################################################################
# Router introspection tests
####################################################################


class TestLearningRouter:
    """Tests that the learning module's router is correctly configured."""

    def test_router_has_expected_route_count(self) -> None:
        """The learning router registers 30 routes."""
        routes = learning_mod.router.routes
        assert (
            len(routes) == 30
        ), f"Expected 30 routes on learning router, got {len(routes)}"

    def test_router_includes_all_learn_paths(self) -> None:
        """All known learn pages exist as registered routes."""
        registered_paths = {r.path for r in learning_mod.router.routes}
        for path, _template, _text in LEARN_PAGES:
            # Strip /v1 prefix — router paths are relative
            suffix = path.replace("/v1", "", 1)
            assert (
                suffix in registered_paths
            ), f"Route {suffix} not found in learning router"

    def test_invalid_learn_path_not_in_router(self) -> None:
        """The non-existent page is NOT a registered route."""
        suffix = INVALID_PAGE.replace("/v1", "", 1)
        registered_paths = {r.path for r in learning_mod.router.routes}
        assert (
            suffix not in registered_paths
        ), f"Route {suffix} should not exist in learning router"


####################################################################
# Arc and utility function tests
####################################################################


class TestArcContext:
    """Tests for the ``_arc_context`` helper function."""

    def test_arc_context_first(self) -> None:
        """First item has no ``prev`` and a valid ``next``."""
        ctx = learning_mod._arc_context("data-fundamentals")
        assert ctx["current_key"] == "data-fundamentals"
        assert ctx["current_index"] == 0
        assert ctx["prev"] is None
        assert ctx["next"] is not None
        assert ctx["next"]["key"] == "tokenization"

    def test_arc_context_middle(self) -> None:
        """Middle item has both ``prev`` and ``next``."""
        ctx = learning_mod._arc_context("attention")
        assert ctx["current_key"] == "attention"
        assert ctx["current_index"] == 5
        assert ctx["prev"] is not None
        assert ctx["prev"]["key"] == "autograd"
        assert ctx["next"] is not None
        assert ctx["next"]["key"] == "loss"

    def test_arc_context_last(self) -> None:
        """Last item has a valid ``prev`` and no ``next``."""
        ctx = learning_mod._arc_context("service-management")
        assert ctx["current_key"] == "service-management"
        assert ctx["current_index"] == 26
        assert ctx["prev"] is not None
        assert ctx["prev"]["key"] == "configuration"
        assert ctx["next"] is None

    def test_arc_context_unknown(self) -> None:
        """An unknown key returns index -1 with no prev/next."""
        ctx = learning_mod._arc_context("unknown-key")
        assert ctx["current_key"] == "unknown-key"
        assert ctx["current_index"] == -1
        assert ctx["prev"] is None
        assert ctx["next"] is None


class TestRelatedLessons:
    """Tests for the ``related_lessons`` helper function."""

    def test_related_lessons_valid_keys(self) -> None:
        """Known keys resolve to lesson entries in requested order."""
        result = learning_mod.related_lessons("tokenization", "embeddings")
        assert len(result) == 2
        assert result[0]["key"] == "tokenization"
        assert result[1]["key"] == "embeddings"

    def test_related_lessons_skips_unknown_keys(self) -> None:
        """Unknown keys are silently skipped."""
        result = learning_mod.related_lessons("nonexistent", "tokenization")
        assert len(result) == 1
        assert result[0]["key"] == "tokenization"

    def test_related_lessons_empty(self) -> None:
        """Empty input returns an empty list."""
        result = learning_mod.related_lessons()
        assert result == []

    def test_related_lessons_all_unknown(self) -> None:
        """All unknown keys returns an empty list."""
        result = learning_mod.related_lessons("foo", "bar", "baz")
        assert result == []


class TestLearningArcData:
    """Tests for the static ``LEARNING_ARC`` data integrity."""

    def test_learning_arc_keys_unique(self) -> None:
        """Every entry in ``LEARNING_ARC`` has a unique key."""
        keys = [item["key"] for item in learning_mod.LEARNING_ARC]
        assert len(keys) == len(set(keys))

    def test_learning_arc_lessons_excludes_additional_and_ops(self) -> None:
        """``LEARNING_ARC_LESSONS`` does not include additional or ops."""
        lesson_keys = {item["key"] for item in learning_mod.LEARNING_ARC_LESSONS}
        for item in learning_mod.LEARNING_ARC_ADDITIONAL:
            assert (
                item["key"] not in lesson_keys
            ), f"Additional key {item['key']} found in lessons"
        for item in learning_mod.OPS_ARC:
            assert (
                item["key"] not in lesson_keys
            ), f"Ops key {item['key']} found in lessons"

    def test_learning_arc_lessons_plus_ops_covers_learning_arc(self) -> None:
        """Every key in ``LEARNING_ARC`` appears in lessons, additional, or ops."""
        lesson_keys = {item["key"] for item in learning_mod.LEARNING_ARC_LESSONS}
        additional_keys = {item["key"] for item in learning_mod.LEARNING_ARC_ADDITIONAL}
        ops_keys = {item["key"] for item in learning_mod.OPS_ARC}
        covered_keys = lesson_keys | additional_keys | ops_keys
        arc_keys = {item["key"] for item in learning_mod.LEARNING_ARC}
        uncovered = arc_keys - covered_keys
        assert (
            not uncovered
        ), f"LEARNING_ARC keys not covered by lessons/additional/ops: {uncovered}"
