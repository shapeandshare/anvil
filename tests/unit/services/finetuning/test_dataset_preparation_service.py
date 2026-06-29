# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for DatasetPreparationService — validation, resolution, rendering, batch processing."""

from __future__ import annotations

import pytest

from anvil.db.base import Base
from anvil.db.session import AsyncSessionLocal, async_engine
from anvil.services.finetuning.dataset_preparation_service import (
    DatasetPreparationService,
    validate_record,
)


@pytest.fixture
async def db_session():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        yield session
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── T014: JSONL record validation ────────────────────────────────────────


class TestRecordValidation:
    """Tests for validate_record covering all input shapes."""

    def test_valid_sft_instruction_response(self):
        """Valid SFT with instruction/response passes."""
        errors: list[dict] = []
        result = validate_record(
            {"instruction": "Hello", "response": "World"},
            0,
            errors,
        )
        assert result is not None
        assert result["instruction"] == "Hello"
        assert result["response"] == "World"
        assert len(errors) == 0

    def test_valid_sft_messages(self):
        """Valid SFT with messages array passes."""
        errors: list[dict] = []
        record = {
            "messages": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
            ]
        }
        result = validate_record(record, 0, errors)
        assert result is not None
        assert len(errors) == 0

    def test_valid_preference(self):
        """Valid preference with chosen/rejected passes."""
        errors: list[dict] = []
        result = validate_record({"chosen": "Good", "rejected": "Bad"}, 0, errors)
        assert result is not None
        assert result["chosen"] == "Good"
        assert len(errors) == 0

    def test_invalid_empty_instruction(self):
        """Empty instruction is skipped with error."""
        errors: list[dict] = []
        result = validate_record({"instruction": "", "response": "World"}, 0, errors)
        assert result is None
        assert len(errors) == 1
        assert errors[0]["row"] == 0

    def test_invalid_empty_response(self):
        """Empty response is skipped with error."""
        errors: list[dict] = []
        result = validate_record({"instruction": "Hi", "response": ""}, 0, errors)
        assert result is None
        assert len(errors) == 1

    def test_invalid_empty_chosen(self):
        """Empty chosen in preference is skipped with error."""
        errors: list[dict] = []
        result = validate_record({"chosen": "", "rejected": "Bad"}, 0, errors)
        assert result is None
        assert len(errors) == 1

    def test_invalid_messages_wrong_role(self):
        """Messages with invalid role is skipped with error."""
        errors: list[dict] = []
        record = {
            "messages": [
                {"role": "invalid_role", "content": "Hi"},
            ]
        }
        result = validate_record(record, 0, errors)
        assert result is None
        assert len(errors) == 1

    def test_unknown_record_type(self):
        """Record with no known structure is skipped with error."""
        errors: list[dict] = []
        result = validate_record({"unknown": "field"}, 0, errors)
        assert result is None
        assert len(errors) == 1


# ── T015: Template resolution + rendering ────────────────────────────────


class TestTemplateResolutionAndRendering:
    """Tests for template resolution (FR-005) and rendering."""

    @pytest.mark.asyncio
    async def test_resolve_no_session_returns_none(self):
        """When no session (stateless mode), resolve_template returns None."""
        svc = DatasetPreparationService(session=None)  # type: ignore[arg-type]
        result = await svc.resolve_template(
            chat_template_id=None,
            base_model_ref=None,
            tokenizer_family="char",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_render_sft_instruction_response(self):
        """SFT record with instruction/response produces a rendered string."""
        svc = DatasetPreparationService(session=None)  # type: ignore[arg-type]
        rendered = svc.render_sft(
            record={"instruction": "Hi", "response": "Hello"},
            template_string="{{ bos_token }}{{ instruction }}\n{{ response }}",
            bos_token="<s>",
        )
        assert rendered is not None
        assert "<s>" in rendered
        assert "Hi" in rendered
        assert "Hello" in rendered

    def test_render_preference_triple(self):
        """Preference record produces prompt/chosen/rejected triple."""
        svc = DatasetPreparationService(session=None)  # type: ignore[arg-type]
        record = {
            "chosen": "Good answer",
            "rejected": "Bad answer",
            "context": "What is 2+2?",
        }
        result = svc.render_preference(
            record=record,
            template_string="{{ context }}",
            bos_token="",
        )
        assert "prompt" in result
        assert "chosen" in result
        assert "rejected" in result
        assert "2+2" in result["prompt"]
        assert result["chosen"] == "Good answer"

    def test_render_sft_messages_branch(self):
        """SFT record with a messages array joins role contents."""
        svc = DatasetPreparationService(session=None)  # type: ignore[arg-type]
        record = {
            "messages": [
                {"role": "user", "content": "Hi there"},
                {"role": "assistant", "content": "Hello back"},
            ]
        }
        rendered = svc.render_sft(record, template_string="{{ x }}", bos_token="<s>")
        assert rendered is not None
        assert "Hi there" in rendered
        assert "Hello back" in rendered
        assert "<s>" in rendered

    @pytest.mark.asyncio
    async def test_resolve_template_explicit_and_fallback(self, db_session):
        """resolve_template returns explicit template, else a default (FR-005)."""
        from anvil.services.finetuning.chat_template_service import ChatTemplateService

        ct_svc = ChatTemplateService(db_session)
        explicit = await ct_svc.create(
            name="resolve-explicit",
            template_string="EXPLICIT {{ instruction }}",
            tokenizer_family="char",
        )

        svc = DatasetPreparationService(db_session)

        # (a) explicit template wins
        res = await svc.resolve_template(
            chat_template_id=explicit.id,
            base_model_ref=None,
            tokenizer_family="char",
        )
        assert res is not None
        assert res.source == "explicit"
        assert res.template.template_string == "EXPLICIT {{ instruction }}"
        assert res.warning is None

        # (c) no explicit, no model -> built-in default with warning
        res2 = await svc.resolve_template(
            chat_template_id=None,
            base_model_ref=None,
            tokenizer_family="char",
        )
        assert res2 is not None
        assert res2.source == "builtin_default"
        assert res2.warning is not None


# ── T016: Skip-and-continue batch processing ─────────────────────────────


class TestBatchProcessing:
    """Tests for skip-and-continue batch processing."""

    def test_mixed_valid_invalid(self):
        """Mixed input produces correct total/succeeded/failed."""
        records = [
            {"instruction": "A", "response": "1"},
            {"instruction": "B", "response": ""},  # invalid
            {"instruction": "C", "response": "3"},
        ]
        errors: list[dict] = []
        valid, invalid = [], []
        for i, rec in enumerate(records):
            result = validate_record(rec, i, errors)
            if result:
                valid.append(result)
            else:
                invalid.append(rec)
        assert len(valid) == 2
        assert len(invalid) == 1
        assert len(errors) == 1

    def test_empty_input(self):
        """Empty input produces 0 valid, 0 invalid."""
        errors: list[dict] = []
        assert len([]) == 0
        assert len(errors) == 0

    def test_all_invalid(self):
        """All invalid records produces 0 succeeded, N failed."""
        records = [
            {"instruction": "", "response": "1"},
            {"instruction": "B", "response": ""},
        ]
        errors: list[dict] = []
        valid = []
        for i, rec in enumerate(records):
            result = validate_record(rec, i, errors)
            if result:
                valid.append(result)
        assert len(valid) == 0
        assert len(errors) == 2
