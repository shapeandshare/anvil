# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for CLI functions, including db_main subcommands."""


from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.cli import db_main

# ======================================================================
# db_main argument parsing (T014, T015, T018)
# ======================================================================


@pytest.fixture
def mock_migration_service():
    """Patch MigrationService so CLI tests don't touch real DB.

    Since db_main() imports MigrationService inside _run(), we
    patch at the CLI binding (anvil.cli.MigrationService).
    """
    with patch("anvil.cli.MigrationService") as mock_cls:
        instance = MagicMock()
        instance.upgrade = AsyncMock(return_value=(None, "abc123"))
        instance.downgrade = AsyncMock(return_value="def456")
        instance.current = AsyncMock(return_value="abc123")
        instance.history = AsyncMock(
            return_value=[
                {"revision": "abc123", "down_revision": "<base>", "message": "Initial"},
            ]
        )
        instance.create_revision = AsyncMock(return_value="new456rev")
        instance.stamp = AsyncMock()
        mock_cls.return_value = instance
        yield instance


class TestDbMain:
    """Verify db_main CLI argument parsing and delegation."""

    def test_upgrade_calls_service(self, mock_migration_service):
        db_main(["upgrade"])
        mock_migration_service.upgrade.assert_awaited_once()

    def test_downgrade_default(self, mock_migration_service):
        db_main(["downgrade"])
        mock_migration_service.downgrade.assert_awaited_once_with("-1")

    def test_downgrade_specific_revision(self, mock_migration_service):
        db_main(["downgrade", "xyz789"])
        mock_migration_service.downgrade.assert_awaited_once_with("xyz789")

    def test_current_calls_service(self, mock_migration_service):
        db_main(["current"])
        mock_migration_service.current.assert_awaited_once()

    def test_history_calls_service(self, mock_migration_service):
        db_main(["history"])
        mock_migration_service.history.assert_awaited_once()

    def test_revision_calls_service(self, mock_migration_service):
        db_main(["revision", "-m", "add table"])
        mock_migration_service.create_revision.assert_awaited_once_with("add table")

    def test_stamp_calls_service(self, mock_migration_service):
        db_main(["stamp", "abc123"])
        mock_migration_service.stamp.assert_awaited_once_with("abc123")

    def test_revision_requires_message(self):
        with pytest.raises(SystemExit):
            db_main(["revision"])

    @patch("anvil.cli.MigrationService")
    def test_migration_error_exits_with_code_1(self, mock_cls: MagicMock):
        from anvil.db.migration_error import MigrationError

        instance = MagicMock()
        instance.upgrade = AsyncMock(side_effect=MigrationError("fail"))
        mock_cls.return_value = instance
        with pytest.raises(SystemExit):
            db_main(["upgrade"])


# ======================================================================
# AnvilWorkbench god class (T016)
# ======================================================================


class TestAnvilWorkbench:
    """Verify AnvilWorkbench god class construction and training access."""

    @patch("anvil.cli.TrainingService")
    def test_workbench_initialises(self, mock_training_cls: MagicMock):
        from anvil.cli import AnvilWorkbench

        wb = AnvilWorkbench()
        mock_training_cls.assert_called_once()
        assert isinstance(wb.training, MagicMock)

    @patch("anvil.cli.TrainingService")
    def test_workbench_training_property(self, mock_training_cls: MagicMock):
        from anvil.cli import AnvilWorkbench

        wb = AnvilWorkbench()
        assert wb.training is mock_training_cls.return_value


# ======================================================================
# serve() — web server startup (T016)
# ======================================================================


class TestServe:
    """Verify serve() configures logging, writes PID file, starts uvicorn."""

    @patch("anvil.cli.get_config")
    @patch("anvil.cli.write_pid")
    @patch("anvil.cli.uvicorn")
    def test_serve_starts_uvicorn(
        self,
        mock_uvicorn: MagicMock,
        mock_write_pid: MagicMock,
        mock_get_config: MagicMock,
    ):
        from pathlib import Path

        from anvil.cli import serve

        mock_get_config.return_value = {
            "port": 8080,
            "log_dir": "logs",
        }
        pid_path = MagicMock(spec=Path)
        mock_write_pid.return_value = pid_path

        serve()
        mock_write_pid.assert_called_once_with("web", pid_dir="logs")
        mock_uvicorn.run.assert_called_once_with(
            "anvil.api.app:app",
            host="0.0.0.0",
            port=8080,
            reload=False,
        )
        pid_path.unlink.assert_called_once_with(missing_ok=True)


# ======================================================================
# show_api_key() (T016)
# ======================================================================


class TestShowApiKey:
    """Verify show_api_key() prints key or exits with error."""

    @patch("anvil.cli.ApiKeyStore")
    def test_prints_key(self, mock_store_cls: MagicMock):
        from anvil.cli import show_api_key

        mock_store_cls.return_value.key = "sk-test-key-123"
        show_api_key()
        # No exception = success

    @patch("anvil.cli.ApiKeyStore")
    def test_exits_when_no_key(self, mock_store_cls: MagicMock):
        from anvil.cli import show_api_key

        mock_store_cls.return_value.key = None
        with pytest.raises(SystemExit):
            show_api_key()


# ======================================================================
# _find_pid_by_port() helper (T016)
# ======================================================================


class TestFindPidByPort:
    """Verify port-to-PID discovery with subprocess mocks."""

    @patch("subprocess.run")
    def test_finds_python_process(self, mock_run: MagicMock):
        from anvil.cli import _find_pid_by_port

        # First call: lsof returns PIDs 1111 2222
        lsof_result = MagicMock()
        lsof_result.returncode = 0
        lsof_result.stdout = "1111\n2222\n"
        # Second call (ps for 1111): python process
        ps_result_1 = MagicMock()
        ps_result_1.stdout = "python3.11\n"
        # Third call (ps for 2222): non-python process
        ps_result_2 = MagicMock()
        ps_result_2.stdout = "some-service\n"
        mock_run.side_effect = [lsof_result, ps_result_1, ps_result_2]

        result = _find_pid_by_port(8080)
        assert result == [1111]

    @patch("subprocess.run")
    def test_returns_empty_when_no_process(self, mock_run: MagicMock):
        from anvil.cli import _find_pid_by_port

        lsof_result = MagicMock()
        lsof_result.returncode = 1
        lsof_result.stdout = ""
        mock_run.return_value = lsof_result

        result = _find_pid_by_port(8080)
        assert result == []

    @patch("subprocess.run")
    def test_returns_empty_on_timeout(self, mock_run: MagicMock):
        from subprocess import TimeoutExpired

        from anvil.cli import _find_pid_by_port

        mock_run.side_effect = TimeoutExpired("lsof", 5)

        result = _find_pid_by_port(8080)
        assert result == []


# ======================================================================
# _kill_pids() helper (T016)
# ======================================================================


class TestKillPids:
    """Verify PID signal-sending helper."""

    @patch("anvil.cli.os.kill")
    def test_kills_all_pids(self, mock_kill: MagicMock):
        from anvil.cli import _kill_pids

        result = _kill_pids([1111, 2222])
        assert result is True
        assert mock_kill.call_count == 2

    @patch("anvil.cli.os.kill")
    def test_handles_missing_process(self, mock_kill: MagicMock):
        from anvil.cli import _kill_pids

        mock_kill.side_effect = ProcessLookupError
        result = _kill_pids([1111])
        assert result is False

    @patch("anvil.cli.os.kill")
    def test_mixed_success_and_missing(self, mock_kill: MagicMock):
        from anvil.cli import _kill_pids

        mock_kill.side_effect = [None, ProcessLookupError]
        result = _kill_pids([1111, 2222])
        assert result is True


# ======================================================================
# _wait_and_sigkill() helper (T016)
# ======================================================================


class TestWaitAndSigkill:
    """Verify graceful-wait escalation to SIGKILL."""

    @patch("time.monotonic", return_value=100.0)
    @patch("time.sleep")
    @patch("anvil.cli.os.kill")
    @patch("anvil.cli._find_pid_by_port", return_value=[])
    def test_processes_die_gracefully(
        self,
        mock_find: MagicMock,
        mock_kill: MagicMock,
        mock_sleep: MagicMock,
        mock_monotonic: MagicMock,
    ):
        from anvil.cli import _wait_and_sigkill

        # os.kill(pid, 0) will raise ProcessLookupError (already dead)
        mock_kill.side_effect = ProcessLookupError

        _wait_and_sigkill([1111], 8080)
        mock_kill.assert_called_once_with(1111, 0)

    @patch("time.monotonic", side_effect=[x * 0.1 for x in range(100)])
    @patch("time.sleep")
    @patch("anvil.cli.os.kill")
    @patch("anvil.cli._find_pid_by_port", side_effect=[[1111], [1111], []])
    def test_escalates_to_sigkill(
        self,
        mock_find: MagicMock,
        mock_kill: MagicMock,
        mock_sleep: MagicMock,
        mock_monotonic: MagicMock,
    ):
        from signal import SIGKILL

        from anvil.cli import _wait_and_sigkill

        mock_kill.return_value = None

        _wait_and_sigkill([1111], 8080)
        sigkill_calls = [c for c in mock_kill.call_args_list if c[0][1] == SIGKILL]
        assert len(sigkill_calls) == 1


# ======================================================================
# stop() (T016)
# ======================================================================


class TestStop:
    """Verify stop() dispatches to PID-file and port-based shutdown."""

    @patch("anvil.cli.get_config")
    @patch("anvil.cli.kill_pid_file", return_value=False)
    @patch("anvil.cli._find_pid_by_port", return_value=[])
    def test_no_servers_running(
        self,
        mock_find: MagicMock,
        mock_kill_file: MagicMock,
        mock_get_config: MagicMock,
    ):
        from anvil.cli import stop

        mock_get_config.return_value = {
            "port": 8080,
            "mlflow_port": 5001,
            "mlflow_disable_local": False,
            "log_dir": "logs",
        }
        stop()
        mock_kill_file.assert_any_call("web", pid_dir="logs")
        mock_kill_file.assert_any_call("mlflow", pid_dir="logs")

    @patch("anvil.cli.get_config")
    @patch("anvil.cli.kill_pid_file", side_effect=[True, True])
    @patch("anvil.cli._find_pid_by_port", return_value=[])
    def test_stop_via_pid_files(
        self,
        mock_find: MagicMock,
        mock_kill_file: MagicMock,
        mock_get_config: MagicMock,
    ):
        from anvil.cli import stop

        mock_get_config.return_value = {
            "port": 8080,
            "mlflow_port": 5001,
            "mlflow_disable_local": False,
            "log_dir": "logs",
        }
        stop()
        assert mock_kill_file.call_count == 2
        mock_find.assert_called()  # port fallback still runs

    @patch("anvil.cli.get_config")
    @patch("anvil.cli.kill_pid_file", side_effect=[False, False])
    @patch("anvil.cli._find_pid_by_port", side_effect=[[], []])
    def test_stop_port_fallback_no_server(
        self,
        mock_find: MagicMock,
        mock_kill_file: MagicMock,
        mock_get_config: MagicMock,
    ):
        from anvil.cli import stop

        mock_get_config.return_value = {
            "port": 8080,
            "mlflow_port": 5001,
            "mlflow_disable_local": False,
            "log_dir": "logs",
        }
        stop()
        assert mock_find.call_count == 2  # both ports checked

    @patch("anvil.cli.get_config")
    @patch("anvil.cli.kill_pid_file", side_effect=[False, False])
    @patch("anvil.cli._find_pid_by_port", side_effect=[[1111], []])
    @patch("anvil.cli._kill_pids", return_value=True)
    @patch("anvil.cli._wait_and_sigkill")
    def test_stop_port_fallback_kills_web(
        self,
        mock_wait: MagicMock,
        mock_kill_pids: MagicMock,
        mock_find: MagicMock,
        mock_kill_file: MagicMock,
        mock_get_config: MagicMock,
    ):
        from anvil.cli import stop

        mock_get_config.return_value = {
            "port": 8080,
            "mlflow_port": 5001,
            "mlflow_disable_local": True,
            "log_dir": "logs",
        }
        stop()
        from signal import SIGTERM

        mock_kill_pids.assert_called_once_with([1111], SIGTERM)


# ======================================================================
# corpus_main() — all subcommands (T016)
# ======================================================================


class TestCorpusMain:
    """Verify corpus_main() argument parsing and service delegation."""

    @patch(
        "sys.argv",
        [
            "corpus_main",
            "create",
            "/tmp/docs",
            "--name",
            "test-corpus",
            "--description",
            "Test description",
            "--pattern",
            "*.txt",
            "--ignore",
            "*.log",
            "--strategy",
            "windowed",
            "--overlap",
            "0.3",
        ],
    )
    @patch("anvil.cli.AsyncSessionLocal")
    @patch("anvil.cli.CorpusService")
    @patch("anvil.cli.CorpusRepository")
    @patch("anvil.cli.CorpusLoader")
    def test_create(
        self,
        mock_loader_cls: MagicMock,
        mock_repo_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_session_factory: MagicMock,
    ):
        from anvil.cli import corpus_main

        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_corpus = MagicMock()
        mock_corpus.id = 42
        mock_corpus.name = "test-corpus"
        mock_svc_cls.return_value.create = AsyncMock(return_value=mock_corpus)

        corpus_main()
        mock_svc_cls.return_value.create.assert_awaited_once_with(
            name="test-corpus",
            root_path="/tmp/docs",
            description="Test description",
            include_patterns=["*.txt"],
            exclude_patterns=["*.log"],
            chunking_strategy="windowed",
            chunk_overlap=0.3,
        )

    @patch("sys.argv", ["corpus_main", "ingest", "1"])
    @patch("anvil.cli.AsyncSessionLocal")
    @patch("anvil.cli.CorpusService")
    @patch("anvil.cli.CorpusRepository")
    @patch("anvil.cli.CorpusLoader")
    def test_ingest(
        self,
        mock_loader_cls: MagicMock,
        mock_repo_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_session_factory: MagicMock,
    ):
        from anvil.cli import corpus_main

        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_corpus = MagicMock()
        mock_corpus.id = 1
        mock_corpus.file_count = 10
        mock_corpus.document_count = 100
        mock_svc_cls.return_value.ingest = AsyncMock(return_value=(mock_corpus, []))

        corpus_main()
        mock_svc_cls.return_value.ingest.assert_awaited_once_with(1)

    @patch("sys.argv", ["corpus_main", "list"])
    @patch("anvil.cli.AsyncSessionLocal")
    @patch("anvil.cli.CorpusService")
    @patch("anvil.cli.CorpusRepository")
    @patch("anvil.cli.CorpusLoader")
    def test_list_corpora(
        self,
        mock_loader_cls: MagicMock,
        mock_repo_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_session_factory: MagicMock,
    ):
        from types import SimpleNamespace

        from anvil.cli import corpus_main

        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        c1 = SimpleNamespace(
            id=1,
            name="corpus-a",
            file_count=5,
            document_count=50,
            chunking_strategy="windowed",
        )
        c2 = SimpleNamespace(
            id=2,
            name="corpus-b",
            file_count=3,
            document_count=30,
            chunking_strategy="line",
        )
        mock_svc_cls.return_value.list_all = AsyncMock(return_value=[c1, c2])

        corpus_main()
        mock_svc_cls.return_value.list_all.assert_awaited_once()

    @patch("sys.argv", ["corpus_main", "show", "1"])
    @patch("anvil.cli.AsyncSessionLocal")
    @patch("anvil.cli.CorpusService")
    @patch("anvil.cli.CorpusRepository")
    @patch("anvil.cli.CorpusLoader")
    def test_show_found(
        self,
        mock_loader_cls: MagicMock,
        mock_repo_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_session_factory: MagicMock,
    ):
        from anvil.cli import corpus_main

        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_corpus = MagicMock()
        mock_corpus.id = 1
        mock_corpus.name = "test"
        mock_corpus.root_path = "/data"
        mock_corpus.chunking_strategy = "windowed"
        mock_corpus.chunk_overlap = 0.5
        mock_corpus.file_count = 10
        mock_corpus.document_count = 100
        mock_svc_cls.return_value.get = AsyncMock(return_value=mock_corpus)

        corpus_main()
        mock_svc_cls.return_value.get.assert_awaited_once_with(1)

    @patch("sys.argv", ["corpus_main", "show", "999"])
    @patch("anvil.cli.AsyncSessionLocal")
    @patch("anvil.cli.CorpusService")
    @patch("anvil.cli.CorpusRepository")
    @patch("anvil.cli.CorpusLoader")
    def test_show_not_found(
        self,
        mock_loader_cls: MagicMock,
        mock_repo_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_session_factory: MagicMock,
    ):
        from anvil.cli import corpus_main

        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_svc_cls.return_value.get = AsyncMock(return_value=None)

        corpus_main()
        mock_svc_cls.return_value.get.assert_awaited_once_with(999)

    @patch("sys.argv", ["corpus_main", "delete", "1"])
    @patch("anvil.cli.AsyncSessionLocal")
    @patch("anvil.cli.CorpusService")
    @patch("anvil.cli.CorpusRepository")
    @patch("anvil.cli.CorpusLoader")
    def test_delete_found(
        self,
        mock_loader_cls: MagicMock,
        mock_repo_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_session_factory: MagicMock,
    ):
        from anvil.cli import corpus_main

        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_svc_cls.return_value.delete = AsyncMock(return_value=True)

        corpus_main()
        mock_svc_cls.return_value.delete.assert_awaited_once_with(1)

    @patch("sys.argv", ["corpus_main", "delete", "999"])
    @patch("anvil.cli.AsyncSessionLocal")
    @patch("anvil.cli.CorpusService")
    @patch("anvil.cli.CorpusRepository")
    @patch("anvil.cli.CorpusLoader")
    def test_delete_not_found(
        self,
        mock_loader_cls: MagicMock,
        mock_repo_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_session_factory: MagicMock,
    ):
        from anvil.cli import corpus_main

        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_svc_cls.return_value.delete = AsyncMock(return_value=False)

        corpus_main()
        mock_svc_cls.return_value.delete.assert_awaited_once_with(999)

    @patch("sys.argv", ["corpus_main", "files", "1"])
    @patch("anvil.cli.AsyncSessionLocal")
    @patch("anvil.cli.CorpusService")
    @patch("anvil.cli.CorpusRepository")
    @patch("anvil.cli.CorpusLoader")
    def test_files(
        self,
        mock_loader_cls: MagicMock,
        mock_repo_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_session_factory: MagicMock,
    ):
        from anvil.cli import corpus_main

        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        f1 = MagicMock(relative_path="doc1.txt", language="python", line_count=42)
        f2 = MagicMock(relative_path="doc2.md", language="markdown", line_count=10)
        mock_svc_cls.return_value.get_files = AsyncMock(return_value=[f1, f2])

        corpus_main()
        mock_svc_cls.return_value.get_files.assert_awaited_once_with(1)


# ======================================================================
# bootstrap_datasets_main() (T001, T016)
# ======================================================================


class TestBootstrapDatasets:
    """Verify bootstrap_datasets_main() dry-run and live flows."""

    @patch("sys.argv", ["bootstrap_datasets_main", "--dry-run"])
    @patch("anvil.cli.AsyncSessionLocal")
    @patch("anvil.cli.DemoBootstrapService")
    def test_dry_run(
        self,
        mock_bootstrap_cls: MagicMock,
        mock_session_factory: MagicMock,
    ):
        from anvil.cli import bootstrap_datasets_main

        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_result = MagicMock()
        mock_result.errors = []
        mock_result.corpora_created = 3
        mock_result.datasets_created = 2
        mock_result.corpora_skipped = 1
        mock_result.datasets_skipped = 0
        mock_bootstrap_cls.return_value.bootstrap_all = AsyncMock(
            return_value=mock_result
        )

        bootstrap_datasets_main()
        mock_bootstrap_cls.return_value.bootstrap_all.assert_awaited_once()

    @patch("sys.argv", ["bootstrap_datasets_main"])
    @patch("anvil.cli.AsyncSessionLocal")
    @patch("anvil.cli.DemoBootstrapService")
    def test_live_no_errors(
        self,
        mock_bootstrap_cls: MagicMock,
        mock_session_factory: MagicMock,
    ):
        from anvil.cli import bootstrap_datasets_main

        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_result = MagicMock()
        mock_result.errors = []
        mock_result.corpora_created = 2
        mock_result.datasets_created = 1
        mock_result.corpora_skipped = 0
        mock_result.datasets_skipped = 0
        mock_result.total_time_ms = 1500
        mock_bootstrap_cls.return_value.bootstrap_all = AsyncMock(
            return_value=mock_result
        )

        with pytest.raises(SystemExit):
            bootstrap_datasets_main()
        mock_session.commit.assert_awaited_once()

    @patch("sys.argv", ["bootstrap_datasets_main"])
    @patch("anvil.cli.AsyncSessionLocal")
    @patch("anvil.cli.DemoBootstrapService")
    def test_live_with_errors(
        self,
        mock_bootstrap_cls: MagicMock,
        mock_session_factory: MagicMock,
    ):
        from anvil.cli import bootstrap_datasets_main

        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_result = MagicMock()
        mock_result.errors = ["Failed to parse xyz"]
        mock_result.corpora_created = 0
        mock_result.datasets_created = 0
        mock_result.corpora_skipped = 1
        mock_result.datasets_skipped = 0
        mock_result.total_time_ms = 500
        mock_bootstrap_cls.return_value.bootstrap_all = AsyncMock(
            return_value=mock_result
        )

        with pytest.raises(SystemExit):
            bootstrap_datasets_main()
        mock_session.rollback.assert_awaited_once()


# ======================================================================
# _load_docs() helper (T016)
# ======================================================================


class TestLoadDocs:
    """Verify _load_docs() dispatches to CorpusService or DemoBootstrapService."""

    @patch("anvil.cli.AsyncSessionLocal")
    @patch("anvil.cli.CorpusService")
    @patch("anvil.cli.CorpusRepository")
    @patch("anvil.cli.CorpusLoader")
    def test_with_corpus_id(
        self,
        mock_loader_cls: MagicMock,
        mock_repo_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_session_factory: MagicMock,
    ):
        from anvil.cli import _load_docs

        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_svc_cls.return_value.load_docs = AsyncMock(return_value=["doc1", "doc2"])

        result = _load_docs(corpus_id=42)
        assert result == ["doc1", "doc2"]
        mock_svc_cls.return_value.load_docs.assert_awaited_once_with(42)

    @patch("anvil.cli.AsyncSessionLocal")
    @patch("anvil.cli.CorpusService")
    @patch("anvil.cli.CorpusRepository")
    @patch("anvil.cli.CorpusLoader")
    @patch("anvil.cli.DemoBootstrapService")
    def test_without_corpus_id(
        self,
        mock_demo_cls: MagicMock,
        mock_loader_cls: MagicMock,
        mock_repo_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_session_factory: MagicMock,
    ):
        from anvil.cli import _load_docs

        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_corpus = MagicMock()
        mock_corpus.id = 1
        mock_demo_cls.return_value.get_default_corpus = AsyncMock(
            return_value=mock_corpus
        )
        mock_svc_cls.return_value.load_docs = AsyncMock(return_value=["default-doc"])

        result = _load_docs(corpus_id=None)
        assert result == ["default-doc"]
        mock_svc_cls.return_value.load_docs.assert_awaited_once_with(1)

    @patch("anvil.cli.AsyncSessionLocal")
    @patch("anvil.cli.DemoBootstrapService")
    def test_without_corpus_id_raises_when_no_demo(
        self,
        mock_demo_cls: MagicMock,
        mock_session_factory: MagicMock,
    ):
        from anvil.cli import _load_docs

        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_demo_cls.return_value.get_default_corpus = AsyncMock(return_value=None)

        with pytest.raises(RuntimeError, match="No demo corpus found"):
            _load_docs(corpus_id=None)


# ======================================================================
# train() — training CLI (T016)
# ======================================================================


class TestTrain:
    """Verify train() argument parsing, service setup, and event loop."""

    @patch("sys.exit")
    @patch("anvil.cli.TrainingService")
    @patch("anvil.cli.TrackingService")
    @patch("anvil.cli.resolve_backend")
    def test_basic_flow(
        self,
        mock_resolve: MagicMock,
        mock_tracking_cls: MagicMock,
        mock_training_cls: MagicMock,
        mock_exit: MagicMock,
    ):
        import asyncio

        from anvil.cli import train

        mock_resolve.return_value = {
            "engine": "local-stdlib",
            "device": "cpu",
            "backend": "auto",
        }

        tracking_instance = mock_tracking_cls.return_value
        tracking_instance.start_run = AsyncMock(return_value="run_abc")
        tracking_instance.log_metric = AsyncMock()
        tracking_instance.finish_run = AsyncMock()
        tracking_instance.log_final_metric = AsyncMock()
        tracking_instance.register_source_model = AsyncMock()

        training_instance = mock_training_cls.return_value
        training_instance.reserve_run = MagicMock(return_value="local_001")
        training_instance.start_training = AsyncMock()

        queue: asyncio.Queue = asyncio.Queue()
        queue.put_nowait(
            {
                "event": "complete",
                "data": '{"step": 1000, "final_loss": 0.1234, "device": "cpu", "samples": ["hello world"]}',
            }
        )
        training_instance.get_queue = MagicMock(return_value=queue)

        train()
        mock_resolve.assert_called_once_with(
            {"compute_backend": "auto", "device": None}
        )
        tracking_instance.start_run.assert_awaited_once()
        training_instance.start_training.assert_awaited_once()
        mock_exit.assert_called_once_with(0)

    @patch("sys.exit")
    @patch("anvil.cli.TrainingService")
    @patch("anvil.cli.TrackingService")
    @patch("anvil.cli.resolve_backend")
    def test_training_error(
        self,
        mock_resolve: MagicMock,
        mock_tracking_cls: MagicMock,
        mock_training_cls: MagicMock,
        mock_exit: MagicMock,
    ):
        from anvil.cli import train

        mock_resolve.return_value = {
            "engine": "local-stdlib",
            "device": "cpu",
            "backend": "auto",
        }

        tracking_instance = mock_tracking_cls.return_value
        tracking_instance.start_run = AsyncMock(return_value="run_abc")
        tracking_instance.fail_run = AsyncMock()

        training_instance = mock_training_cls.return_value
        training_instance.reserve_run = MagicMock(return_value="local_001")
        training_instance.start_training = AsyncMock(
            side_effect=ValueError("training failed")
        )

        with pytest.raises(ValueError):
            train()
        tracking_instance.fail_run.assert_awaited_once()
        mock_exit.assert_not_called()

    @patch("sys.exit")
    @patch("anvil.cli.TrainingService")
    @patch("anvil.cli.TrackingService")
    @patch("anvil.cli.resolve_backend")
    def test_queue_metrics_then_complete(
        self,
        mock_resolve: MagicMock,
        mock_tracking_cls: MagicMock,
        mock_training_cls: MagicMock,
        mock_exit: MagicMock,
    ):
        import asyncio

        from anvil.cli import train

        mock_resolve.return_value = {
            "engine": "local-stdlib",
            "device": "cpu",
            "backend": "auto",
        }

        tracking_instance = mock_tracking_cls.return_value
        tracking_instance.start_run = AsyncMock(return_value="run_abc")
        tracking_instance.log_metric = AsyncMock()
        tracking_instance.finish_run = AsyncMock()
        tracking_instance.log_final_metric = AsyncMock()
        tracking_instance.register_source_model = AsyncMock()

        training_instance = mock_training_cls.return_value
        training_instance.reserve_run = MagicMock(return_value="local_001")
        training_instance.start_training = AsyncMock()

        queue: asyncio.Queue = asyncio.Queue()
        queue.put_nowait(
            {
                "event": "metrics",
                "data": '{"step": 500, "loss": 0.5678, "device": "cpu"}',
            }
        )
        queue.put_nowait(
            {
                "event": "complete",
                "data": '{"step": 1000, "final_loss": 0.1234, "device": "cpu", "samples": ["sample1"]}',
            }
        )
        training_instance.get_queue = MagicMock(return_value=queue)

        train()
        mock_resolve.assert_called_once()
        mock_exit.assert_called_once_with(0)

    @patch("sys.exit")
    @patch("anvil.cli.TrainingService")
    @patch("anvil.cli.TrackingService")
    @patch("anvil.cli.resolve_backend")
    def test_queue_error_event(
        self,
        mock_resolve: MagicMock,
        mock_tracking_cls: MagicMock,
        mock_training_cls: MagicMock,
        mock_exit: MagicMock,
    ):
        import asyncio

        from anvil.cli import train

        mock_resolve.return_value = {
            "engine": "local-stdlib",
            "device": "cpu",
            "backend": "auto",
        }

        tracking_instance = mock_tracking_cls.return_value
        tracking_instance.start_run = AsyncMock(return_value="run_abc")
        tracking_instance.log_metric = AsyncMock()
        tracking_instance.finish_run = AsyncMock()
        tracking_instance.log_final_metric = AsyncMock()
        tracking_instance.register_source_model = AsyncMock()

        training_instance = mock_training_cls.return_value
        training_instance.reserve_run = MagicMock(return_value="local_001")
        training_instance.start_training = AsyncMock()

        queue: asyncio.Queue = asyncio.Queue()
        queue.put_nowait(
            {
                "event": "error",
                "data": "Something went wrong",
            }
        )
        training_instance.get_queue = MagicMock(return_value=queue)

        train()
        mock_exit.assert_called_once_with(0)
