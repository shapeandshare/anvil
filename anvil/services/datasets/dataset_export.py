# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Dataset export service — exports dataset samples to text-based formats.

Provides the ``DatasetExportService`` class which reads active samples
from a dataset and streams them in TXT, CSV, or JSONL format.
"""

import json
from collections.abc import AsyncIterator, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models.sample import Sample
from ...db.repositories.curation import SampleRepository
from ...storage.local import LocalFileStore


class DatasetExportService:
    """Exports dataset samples to plaintext-based formats.

    Supports TXT (one sample per line), CSV (``index,text`` format),
    and JSONL (one JSON object per line). Reads sample content from
    the file store on demand.
    """

    def __init__(
        self,
        session: AsyncSession,
        dataset_id: int,
        store: LocalFileStore | None = None,
    ):
        """Initialise the export service.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session for database access.
        dataset_id : int
            ID of the dataset to export.
        store : LocalFileStore, optional
            File store for reading sample content. Defaults to a new
            ``LocalFileStore`` at ``"data/datasets"``.
        """
        self._session = session
        self._dataset_id = dataset_id
        self._store = store or LocalFileStore("data/datasets")
        self._sample_repo = SampleRepository(session)

    async def _get_active_samples(self) -> Sequence[Sample]:
        """Fetch all active (non-removed) samples for the dataset.

        Returns
        -------
        Sequence[Sample]
            Active sample records ordered by index.
        """
        return await self._sample_repo.get_active_texts(self._dataset_id)

    async def _read_sample_text(self, sample: Sample) -> str:
        """Read a sample's text content from the file store.

        Parameters
        ----------
        sample : Sample
            The sample record whose content to read.

        Returns
        -------
        str
            The decoded UTF-8 text content.
        """
        text_bytes = b""
        async for chunk in self._store.get(sample.file_path):
            text_bytes += chunk
        return text_bytes.decode("utf-8")

    async def export_txt(self) -> AsyncIterator[str]:
        """Export samples as plain text, one sample per line.

        Yields
        ------
        str
            Each sample's text content followed by a newline.
        """
        samples = await self._get_active_samples()
        for s in samples:
            text = await self._read_sample_text(s)
            yield text + "\n"

    async def export_csv(self) -> AsyncIterator[str]:
        """Export samples as CSV with ``index,text`` columns.

        Escapes double-quotes in sample text per CSV convention.

        Yields
        ------
        str
            CSV header and data rows, one per sample.
        """
        samples = await self._get_active_samples()
        yield "index,text\n"
        for s in samples:
            text = await self._read_sample_text(s)
            escaped = text.replace('"', '""')
            yield f'{s.index},"{escaped}"\n'

    async def export_jsonl(self) -> AsyncIterator[str]:
        """Export samples as JSONL, one JSON object per line.

        Each line contains ``{"index": ..., "text": ...}``.

        Yields
        ------
        str
            JSON-encoded sample object followed by a newline.
        """
        samples = await self._get_active_samples()
        for s in samples:
            text = await self._read_sample_text(s)
            yield json.dumps({"index": s.index, "text": text}) + "\n"
