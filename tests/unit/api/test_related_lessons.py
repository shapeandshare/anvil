# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for the related-lessons CTA helper and its rendering on pages."""

import pytest
from httpx import ASGITransport, AsyncClient

from anvil.api.app import app
from anvil.api.v1.learning import LEARNING_ARC, related_lessons


def test_related_lessons_preserves_requested_order():
    """``related_lessons`` returns entries in the order of the given keys."""
    result = related_lessons("sampling", "attention", "embeddings")
    assert [item["key"] for item in result] == ["sampling", "attention", "embeddings"]


def test_related_lessons_skips_unknown_keys():
    """Unknown keys are silently skipped, known keys are kept."""
    result = related_lessons("sampling", "does-not-exist", "loss")
    assert [item["key"] for item in result] == ["sampling", "loss"]


def test_related_lessons_entries_have_path_and_title():
    """Each returned entry carries a renderable ``path`` and ``title``."""
    for item in related_lessons(*[lesson["key"] for lesson in LEARNING_ARC]):
        assert item["path"].startswith("/v1/learn/")
        assert item["title"]


def test_related_lessons_empty_when_no_keys():
    """Calling with no keys yields an empty list (renders nothing)."""
    assert related_lessons() == []


@pytest.mark.asyncio
async def test_training_page_renders_related_lessons_row():
    """The training page renders the related-lessons CTA row with lesson links."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/training-page")
    assert response.status_code == 200
    body = response.text
    assert "related-lessons" in body
    assert "/v1/learn/parameters" in body
    assert "/v1/learn/architecture" in body
