# Copyright © 2026 Josh Burt
# one-class:allow — TemplateResolution is the tightly-coupled return type of DatasetPreparationService.resolve_template()
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""DatasetPreparationService — validation, template resolution, rendering, and batch processing."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .chat_template_service import ChatTemplateService


def validate_record(
    record: dict[str, Any],
    row_index: int,
    errors: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Validate a single record against its declared shape.

    Supports SFT (``instruction``/``response`` or ``messages`` array) and
    preference (``chosen``/``rejected``). Invalid records are skipped
    (skip-and-continue per FR-002).

    Parameters
    ----------
    record : dict
        The parsed JSONL record.
    row_index : int
        Zero-based row index for error reporting.
    errors : list[dict]
        Accumulator for per-record error details. Appended to on failure.

    Returns
    -------
    dict or None
        The validated record, or ``None`` if validation failed.
    """
    # SFT: instruction/response
    if "instruction" in record or "response" in record:
        instruction = record.get("instruction", "")
        response = record.get("response", "")
        if (
            not instruction
            or not isinstance(instruction, str)
            or not instruction.strip()
        ):
            errors.append({"row": row_index, "error": "Empty or missing 'instruction'"})
            return None
        if not response or not isinstance(response, str) or not response.strip():
            errors.append({"row": row_index, "error": "Empty or missing 'response'"})
            return None
        return record

    # SFT: messages array (role-based)
    if "messages" in record:
        messages = record["messages"]
        if not isinstance(messages, list) or len(messages) == 0:
            errors.append({"row": row_index, "error": "Empty or non-list 'messages'"})
            return None
        valid_roles = {"user", "assistant", "system"}
        for msg in messages:
            role = msg.get("role", "")
            if role not in valid_roles:
                errors.append(
                    {"row": row_index, "error": f"Invalid role '{role}' in messages"}
                )
                return None
            content = msg.get("content", "")
            if not content or not isinstance(content, str) or not content.strip():
                errors.append(
                    {"row": row_index, "error": f"Empty content for role '{role}'"}
                )
                return None
        return record

    # Preference: chosen/rejected
    if "chosen" in record or "rejected" in record:
        chosen = record.get("chosen", "")
        rejected = record.get("rejected", "")
        if not chosen or not isinstance(chosen, str) or not chosen.strip():
            errors.append({"row": row_index, "error": "Empty or missing 'chosen'"})
            return None
        if not rejected or not isinstance(rejected, str) or not rejected.strip():
            errors.append({"row": row_index, "error": "Empty or missing 'rejected'"})
            return None
        return record

    # Unknown structure
    errors.append(
        {
            "row": row_index,
            "error": "Record does not match any known shape (SFT or preference)",
        }
    )
    return None


class DatasetPreparationService:
    """Service for preparing fine-tuning datasets.

    Orchestrates template resolution, record validation, rendering, and
    batch processing for turning raw instruction examples into chat-template-
    rendered training records.

    Parameters
    ----------
    session : AsyncSession or None
        SQLAlchemy async session, or ``None`` for stateless operations
        (validation, rendering).
    """

    def __init__(self, session: AsyncSession | None) -> None:
        self._session = session

    async def resolve_template(
        self,
        chat_template_id: int | None,
        base_model_ref: int | None,
        tokenizer_family: str,
    ) -> TemplateResolution | None:
        """Resolve the chat template following FR-005 priority order.

        (a) explicit template → (b) model-derived → (c) built-in default + warning.

        Parameters
        ----------
        chat_template_id : int or None
            An explicitly specified template ID (FR-005a).
        base_model_ref : int or None
            The base model reference (FR-005b).
        tokenizer_family : str
            Tokenizer family for fallback selection (FR-005c).

        Returns
        -------
        TemplateResolution or None
            The resolved template with optional warning, or ``None`` if
            no session is available for deriving/caching defaults.
        """
        if self._session is None:
            return None

        svc = ChatTemplateService(self._session)

        # (a): explicit template
        if chat_template_id is not None:
            template = await svc.get(chat_template_id)
            if template is not None:
                return TemplateResolution(
                    template=template, warning=None, source="explicit"
                )

        # (b/c): model-derived or built-in default
        template, warning = await svc.get_default_template_for_model(
            base_model_ref=base_model_ref,
            tokenizer_family=tokenizer_family,
        )
        source = "builtin_default" if warning else "model_derived"
        return TemplateResolution(template=template, warning=warning, source=source)

    @staticmethod
    def render_sft(
        record: dict[str, Any],
        template_string: str,
        bos_token: str = "",
    ) -> str | None:
        """Render an SFT record using the template string.

        Simple string-level substitution for the ``instruction`` and
        ``response`` fields. For ``messages``-based records, joins roles
        sequentially.

        Parameters
        ----------
        record : dict
            The validated SFT record.
        template_string : str
            The chat template string with ``{{ instruction }}`` and
            ``{{ response }}`` placeholders.
        bos_token : str
            Beginning-of-sequence token to prepend.

        Returns
        -------
        str or None
            The rendered prompt string, or ``None`` if rendering fails.
        """
        if "messages" in record:
            parts = [bos_token]
            for msg in record["messages"]:
                parts.append(msg["content"])
            return "\n".join(parts)

        instruction = record.get("instruction", "")
        response = record.get("response", "")
        rendered = (
            template_string.replace("{{ instruction }}", instruction)
            .replace("{{ response }}", response)
            .replace("{{ bos_token }}", bos_token)
        )
        return rendered

    @staticmethod
    def render_preference(
        record: dict[str, Any],
        template_string: str,
        bos_token: str = "",
    ) -> dict[str, Any]:
        """Render a preference record into a prompt/chosen/rejected triple.

        The shared ``context`` (or empty string) is rendered with the
        template, producing a consistent prompt for both sides.

        Parameters
        ----------
        record : dict
            The validated preference record with ``chosen``, ``rejected``,
            and optional ``context``.
        template_string : str
            The chat template string.
        bos_token : str
            Beginning-of-sequence token.

        Returns
        -------
        dict
            A dict with ``prompt``, ``chosen``, and ``rejected`` keys.
        """
        context = record.get("context", "")
        prompt = template_string.replace("{{ context }}", context).replace(
            "{{ bos_token }}", bos_token
        )
        return {
            "prompt": prompt,
            "chosen": record["chosen"],
            "rejected": record["rejected"],
        }


class TemplateResolution:
    """The result of resolving a chat template.

    Parameters
    ----------
    template : ChatTemplate
        The resolved template.
    warning : str or None
        Warning message if a fallback was used (``None`` for explicit).
    source : str
        Which FR-005 path was taken: ``"explicit"``, ``"model_derived"``,
        or ``"builtin_default"``.
    """

    def __init__(
        self,
        template: object,
        warning: str | None,
        source: str,
    ) -> None:
        self.template = template
        self.warning = warning
        self.source = source
