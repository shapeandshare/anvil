import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.repositories.experiments import ExperimentRepository
from anvil.db.session import AsyncSessionLocal
from anvil.services.tracking import TrackingService


class _FakeMLflowClient:
    def __init__(self, tracking_uri: str):
        self._tracking_uri = tracking_uri
        self.runs: dict[str, str] = {}
        self.terminated: dict[str, str] = {}
        self._experiment_id: str | None = None

    def get_experiment_by_name(self, name):
        from unittest.mock import MagicMock

        if self._experiment_id is None:
            return None
        return MagicMock(experiment_id=self._experiment_id)

    def create_experiment(self, name):
        self._experiment_id = "0"
        return "0"

    def search_runs(self, experiment_ids, filter_string):
        from unittest.mock import MagicMock

        results = []
        for run_id, status in self.runs.items():
            if status == "RUNNING":
                mock = MagicMock()
                mock.info.run_id = run_id
                results.append(mock)
        return results

    def set_terminated(self, run_id, status):
        self.terminated[run_id] = status
        self.runs[run_id] = status

    def log_batch(self, run_id, params=None, metrics=None, tags=None):
        pass

    def create_run(self, experiment_id, run_name=None, tags=None):
        from unittest.mock import MagicMock

        run_id = f"mlflow_{len(self.terminated) + 1}"
        self.runs[run_id] = "RUNNING"
        return MagicMock(info=MagicMock(run_id=run_id))

    def log_metric(self, run_id, key, value, step=None):
        pass

    def log_artifact(self, run_id, local_path):
        pass


@pytest.fixture
def _fake_client():
    return _FakeMLflowClient("http://127.0.0.1:5000")


@pytest.mark.asyncio
async def test_reconcile_orphans_marks_local_experiments_failed(
    session: AsyncSession, _fake_client: _FakeMLflowClient
):
    repo = ExperimentRepository(session)
    exp = await repo.create_running(
        config_id=1,
        run_name="orphan-test",
        mlflow_run_id="mlflow_orphan_1",
        engine_backend="stdlib",
        device="cpu",
    )
    await session.commit()
    exp_id = exp.id

    _fake_client.runs["mlflow_orphan_1"] = "RUNNING"

    svc = TrackingService(
        tracking_uri="http://127.0.0.1:5000",
        client_factory=lambda uri: _fake_client,
    )
    svc._lazy_init()
    reconciled = await svc.reconcile_orphans()

    assert "mlflow_orphan_1" in reconciled
    assert _fake_client.terminated.get("mlflow_orphan_1") == "KILLED"

    async with AsyncSessionLocal() as fresh_session:
        fresh_repo = ExperimentRepository(fresh_session)
        updated = await fresh_repo.get(exp_id)
        assert updated.status == "failed"
        assert updated.error_message == "interrupted/terminated"
        assert updated.completed_at is not None


@pytest.mark.asyncio
async def test_reconcile_orphans_idempotent(
    session: AsyncSession, _fake_client: _FakeMLflowClient
):
    repo = ExperimentRepository(session)
    exp = await repo.create_running(
        config_id=1,
        run_name="idempotent-test",
        mlflow_run_id="mlflow_idempotent_1",
    )
    await session.commit()
    exp_id = exp.id

    _fake_client.runs["mlflow_idempotent_1"] = "RUNNING"

    svc = TrackingService(
        tracking_uri="http://127.0.0.1:5000",
        client_factory=lambda uri: _fake_client,
    )
    svc._lazy_init()

    reconciled1 = await svc.reconcile_orphans()
    assert "mlflow_idempotent_1" in reconciled1

    reconciled2 = await svc.reconcile_orphans()
    assert len(reconciled2) == 0

    async with AsyncSessionLocal() as fresh_session:
        fresh_repo = ExperimentRepository(fresh_session)
        updated = await fresh_repo.get(exp_id)
        assert updated.status == "failed"
        assert updated.error_message == "interrupted/terminated"


@pytest.mark.asyncio
async def test_reconcile_orphans_skips_finished_runs(
    session: AsyncSession, _fake_client: _FakeMLflowClient
):
    repo = ExperimentRepository(session)
    exp = await repo.create_running(
        config_id=1,
        run_name="finished-test",
        mlflow_run_id="mlflow_finished_1",
    )
    exp_id = exp.id
    await session.commit()
    await repo.mark_finished(
        experiment_id=exp_id,
        final_loss=0.5,
    )
    await session.commit()

    _fake_client.runs["mlflow_finished_1"] = "FINISHED"

    svc = TrackingService(
        tracking_uri="http://127.0.0.1:5000",
        client_factory=lambda uri: _fake_client,
    )
    svc._lazy_init()

    reconciled = await svc.reconcile_orphans()
    assert len(reconciled) == 0
    assert "mlflow_finished_1" not in _fake_client.terminated

    async with AsyncSessionLocal() as fresh_session:
        fresh_repo = ExperimentRepository(fresh_session)
        updated = await fresh_repo.get(exp_id)
        assert updated.status == "finished"


def test_lifespan_calls_reconcile_orphans_source():
    from pathlib import Path

    src = Path("anvil/api/app.py").read_text()
    assert "reconcile_orphans" in src
    assert "TrackingService" in src
