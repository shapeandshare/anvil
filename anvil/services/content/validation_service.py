# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Validation gates for staged content batches.

``ValidationService`` provides pre-acceptance checks on staged content
before it is folded into the canonical corpus.  Gates cover UTF-8
readability, size bounds, provenance metadata, intra-batch
deduplication, cross-corpus deduplication, language allowlisting,
and sensitive-info scanning.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from aiofiles import open as async_open  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .staged_entry import StagedEntry
from .validation_report import ValidationProblem, ValidationReport

if TYPE_CHECKING:
    pass  # TYPE_CHECKING-only: avoids ORM import at module level

_MAX_ENTRY_SIZE_BYTES = 100 * 1024 * 1024  # 100 MiB


class ValidationService:
    """Stateless validation gates for staged content ingestion.

    Each method in this service implements a single gate. The public
    :meth:`validate` method runs all gates over a batch of staged
    entries and produces a consolidated report.
    """

    async def validate(
        self,
        incoming: list[StagedEntry],
        /,
        *,
        content_db_session: AsyncSession,
        content_dir: str,
        corpus_slug: str,
    ) -> ValidationReport:
        """Run all validation gates over a batch of staged entries.

        The following gates are applied in order:

        1. **UTF-8 readability** — each blob must decode cleanly as
           UTF-8 text.
        2. **Size bounds** — no single entry may exceed 100 MiB.
        3. **Provenance metadata** — each entry must have a non-empty
           ``path`` and ``content_hash``.
        4. **Intra-batch dedup** — no two entries may share the same
           ``content_hash``.
        5. **Cross-corpus exact dedup** — flags entries whose content
           hash already exists elsewhere in the corpus (warning only).
        6. **Language allowlist** — rejects content containing
           characters beyond U+00FF (non-Latin).
        7. **Sensitive-info scan** — rejects content matching credit
           card, email, or SSN patterns.

        Parameters
        ----------
        incoming : list of StagedEntry
            The batch of staged entries to validate.
        content_db_session : AsyncSession
            SQLAlchemy async session (reserved for future DB-backed
            gates).
        content_dir : str
            Root directory of the content store, used to locate blob
            files for content checks.
        corpus_slug : str
            Slug identifying the target corpus (reserved for future
            corpus-specific rules).

        Returns
        -------
        ValidationReport
            ``ok=True`` when all gates pass, with an empty
            ``problems`` list.  ``ok=False`` when any blocking error
            is found.
        """
        problems: list[ValidationProblem] = []

        # Gate 1 — UTF-8 readability.
        for entry in incoming:
            problem = await self._check_utf8_readable(entry, content_dir=content_dir)
            if problem is not None:
                problems.append(problem)

        # Gate 2 — Size bounds.
        for entry in incoming:
            if entry.size_bytes > _MAX_ENTRY_SIZE_BYTES:
                problems.append(
                    ValidationProblem(
                        gate_name="size_limit",
                        entry_path=entry.path,
                        reason=(
                            f"Entry size {entry.size_bytes} bytes exceeds "
                            f"maximum {_MAX_ENTRY_SIZE_BYTES} bytes"
                        ),
                    )
                )

        # Gate 3 — Provenance metadata.
        for entry in incoming:
            if not entry.path.strip():
                problems.append(
                    ValidationProblem(
                        gate_name="provenance_metadata",
                        entry_path=entry.path,
                        reason="Entry path must be non-empty",
                    )
                )
            if not entry.content_hash.strip():
                problems.append(
                    ValidationProblem(
                        gate_name="provenance_metadata",
                        entry_path=entry.path,
                        reason="Entry content_hash must be non-empty",
                    )
                )

        # Gate 4 — Intra-batch exact dedup.
        seen_hashes: set[str] = set()
        for entry in incoming:
            if entry.content_hash in seen_hashes:
                problems.append(
                    ValidationProblem(
                        gate_name="intra_batch_dedup",
                        entry_path=entry.path,
                        reason=(
                            f"Duplicate content_hash "
                            f"'{entry.content_hash}' in batch"
                        ),
                    )
                )
            seen_hashes.add(entry.content_hash)

        # Gate 5 — Cross-corpus exact dedup (warning).
        problems.extend(
            await self._check_cross_corpus_dedup(
                incoming, content_db_session=content_db_session
            )
        )

        # Gate 6 — Language allowlist.
        problems.extend(
            await self._check_language_allowlist(incoming, content_dir=content_dir)
        )

        # Gate 7 — Sensitive-info scan.
        problems.extend(
            await self._check_sensitive_info(incoming, content_dir=content_dir)
        )

        # Gate 8 — License gate: session-level.  Enforced at session
        # creation by the route handler using GovernanceService.
        # placeholder

        ok = not any(p.severity == "error" for p in problems)
        return ValidationReport(ok=ok, problems=problems)

    async def _check_utf8_readable(
        self,
        entry: StagedEntry,
        *,
        content_dir: str,
    ) -> ValidationProblem | None:
        """Check that a blob is valid UTF-8 text.

        Reads the blob from the content-addressed store and attempts
        a UTF-8 decode.

        Parameters
        ----------
        entry : StagedEntry
            The staged entry whose blob to check.
        content_dir : str
            Root directory of the content store.

        Returns
        -------
        ValidationProblem or None
            A problem describing the failure, or ``None`` if the
            blob is valid UTF-8.
        """
        blob_path = (
            Path(content_dir) / "blobs" / entry.content_hash[:2] / entry.content_hash
        )

        try:
            async with async_open(str(blob_path), "rb") as f:
                raw = await f.read()
            raw.decode("utf-8")
            return None
        except FileNotFoundError:
            return ValidationProblem(
                gate_name="utf8_readability",
                entry_path=entry.path,
                reason=f"Blob file not found at {blob_path}",
            )
        except UnicodeDecodeError:
            return ValidationProblem(
                gate_name="utf8_readability",
                entry_path=entry.path,
                reason="Blob content is not valid UTF-8 text",
            )

    async def _read_blob_content(
        self,
        content_hash: str,
        *,
        content_dir: str,
    ) -> bytes | None:
        """Read blob content from the content-addressed store.

        Parameters
        ----------
        content_hash : str
            SHA-256 hex digest of the blob.
        content_dir : str
            Root directory of the content store.

        Returns
        -------
        bytes or None
            The raw blob content, or ``None`` if the blob file does
            not exist on disk.
        """
        blob_path = Path(content_dir) / "blobs" / content_hash[:2] / content_hash
        try:
            async with async_open(str(blob_path), "rb") as f:
                return await f.read()  # type: ignore[no-any-return]
        except FileNotFoundError:
            return None

    async def _check_cross_corpus_dedup(
        self,
        incoming: list[StagedEntry],
        *,
        content_db_session: AsyncSession,
    ) -> list[ValidationProblem]:
        """Check that no staged content hash already exists in the DB.

        Queries ``ContentEntry`` for any hash that matches an incoming
        entry.  Duplicates produce a warning (not a blocking error).

        Parameters
        ----------
        incoming : list of StagedEntry
            The batch of staged entries to check.
        content_db_session : AsyncSession
            SQLAlchemy async session for DB queries.

        Returns
        -------
        list of ValidationProblem
            Warning-level problems for each duplicate found, or an
            empty list when no duplicates exist.
        """
        problems: list[ValidationProblem] = []
        hashes = [e.content_hash for e in incoming]
        if not hashes:
            return problems

        # Local import to avoid circular import at module level.
        from ...db.models.content_entry import ContentEntry

        result = await content_db_session.execute(
            select(ContentEntry.content_hash)
            .where(ContentEntry.content_hash.in_(hashes))
            .distinct()
        )
        existing: set[str] = {row[0] for row in result.fetchall()}

        for entry in incoming:
            if entry.content_hash in existing:
                problems.append(
                    ValidationProblem(
                        gate_name="cross_corpus_dedup",
                        entry_path=entry.path,
                        reason=(
                            f"Content with hash {entry.content_hash} "
                            "already exists in the corpus."
                        ),
                        severity="warning",
                    )
                )
        return problems

    async def _check_language_allowlist(
        self,
        incoming: list[StagedEntry],
        *,
        content_dir: str,
    ) -> list[ValidationProblem]:
        """Reject entries with characters beyond U+00FF (non-Latin).

        Reads each blob from disk, decodes as UTF-8, and checks
        whether any character has an ordinal greater than 0xFF.  The
        first offending character triggers a blocking error for that
        entry (subsequent characters in the same entry are not
        re-reported).

        Parameters
        ----------
        incoming : list of StagedEntry
            The batch of staged entries to check.
        content_dir : str
            Root directory of the content store.

        Returns
        -------
        list of ValidationProblem
            Error-level problems for each entry containing non-Latin
            characters, or an empty list when all entries pass.
        """
        problems: list[ValidationProblem] = []
        for entry in incoming:
            raw = await self._read_blob_content(
                entry.content_hash, content_dir=content_dir
            )
            if raw is None:
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue  # already caught by the UTF-8 gate
            for ch in text:
                if ord(ch) > 0xFF:
                    problems.append(
                        ValidationProblem(
                            gate_name="language_allowlist",
                            entry_path=entry.path,
                            reason=(
                                "Content contains characters outside "
                                "allowed range (non-Latin detected)."
                            ),
                        )
                    )
                    break
        return problems

    async def _check_sensitive_info(
        self,
        incoming: list[StagedEntry],
        *,
        content_dir: str,
    ) -> list[ValidationProblem]:
        """Scan blob content for credit-card, email, and SSN patterns.

        Applies regex patterns for credit-card numbers, email
        addresses, and US Social Security numbers against each entry's
        decoded text.  An entry may produce multiple problems (one per
        pattern type).

        Parameters
        ----------
        incoming : list of StagedEntry
            The batch of staged entries to check.
        content_dir : str
            Root directory of the content store.

        Returns
        -------
        list of ValidationProblem
            Error-level problems for every pattern match found, or an
            empty list when no sensitive content is detected.
        """
        problems: list[ValidationProblem] = []
        patterns: list[tuple[str, re.Pattern[str]]] = [
            ("credit_card", re.compile(r"\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}")),
            ("email", re.compile(r"[\w.+-]+@[\w-]+\.\w+")),
            ("ssn", re.compile(r"\d{3}-\d{2}-\d{4}")),
        ]
        for entry in incoming:
            raw = await self._read_blob_content(
                entry.content_hash, content_dir=content_dir
            )
            if raw is None:
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue  # already caught by the UTF-8 gate
            for pattern_name, pattern in patterns:
                if pattern.search(text):
                    problems.append(
                        ValidationProblem(
                            gate_name="sensitive_info",
                            entry_path=entry.path,
                            reason=(f"Sensitive content detected: " f"{pattern_name}."),
                        )
                    )
        return problems
