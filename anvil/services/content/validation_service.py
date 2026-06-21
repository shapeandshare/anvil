# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Validation gates for staged content batches.

``ValidationService`` provides pre-acceptance checks on staged content
before it is folded into the canonical corpus.  Gates cover UTF-8
readability, size bounds, provenance metadata, and intra-batch
deduplication.
"""

from __future__ import annotations

from pathlib import Path

from aiofiles import open as async_open
from sqlalchemy.ext.asyncio import AsyncSession

from .staged_entry import StagedEntry
from .validation_report import ValidationProblem, ValidationReport

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
