import csv
import io
import json

from collections.abc import AsyncIterator, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from microgpt.db.models.curation import Sample
from microgpt.db.repositories.curation import SampleRepository
from microgpt.storage.local import LocalFileStore


class DatasetExportService:
    def __init__(
        self,
        session: AsyncSession,
        dataset_id: int,
        store: LocalFileStore | None = None,
    ):
        self._session = session
        self._dataset_id = dataset_id
        self._store = store or LocalFileStore("data/datasets")
        self._sample_repo = SampleRepository(session)

    async def _get_active_samples(self) -> Sequence[Sample]:
        return await self._sample_repo.get_active_texts(self._dataset_id)

    async def _read_sample_text(self, sample: Sample) -> str:
        text_bytes = b""
        async for chunk in self._store.get(sample.file_path):
            text_bytes += chunk
        return text_bytes.decode("utf-8")

    async def export_txt(self) -> AsyncIterator[str]:
        samples = await self._get_active_samples()
        for s in samples:
            text = await self._read_sample_text(s)
            yield text + "\n"

    async def export_csv(self) -> AsyncIterator[str]:
        samples = await self._get_active_samples()
        yield "index,text\n"
        for s in samples:
            text = await self._read_sample_text(s)
            escaped = text.replace('"', '""')
            yield f'{s.index},"{escaped}"\n'

    async def export_jsonl(self) -> AsyncIterator[str]:
        samples = await self._get_active_samples()
        for s in samples:
            text = await self._read_sample_text(s)
            yield json.dumps({"index": s.index, "text": text}) + "\n"