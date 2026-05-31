"""Tests for the JobDetailScreen widget."""

from unittest.mock import MagicMock, patch

import pytest

from slurmhub.config import SSHConfig
from slurmhub.slurm.scontrol import JobDetails
from slurmhub.slurm.squeue import SlurmJob
from slurmhub.slurm.ssh import SSHClient
from slurmhub.tui.widgets.job_detail_screen import JobDetailScreen


@pytest.fixture
def mock_job():
    return SlurmJob(
        job_id="12345",
        name="test-job",
        state="RUNNING",
        time="1:00:00",
        work_dir="/home/user/project",
    )


@pytest.fixture
def mock_ssh_client():
    config = SSHConfig(host="testhost")
    return SSHClient(config)


class TestJobDetailScreen:
    def test_creates_with_job_info(self, mock_job, mock_ssh_client):
        screen = JobDetailScreen(mock_job, mock_ssh_client)
        assert screen.job == mock_job
        assert screen.details is None

    def test_get_log_path_stdout(self, mock_job, mock_ssh_client):
        screen = JobDetailScreen(mock_job, mock_ssh_client)
        screen.details = JobDetails(
            stdout_path="/path/to/out.log",
            stderr_path="/path/to/err.log",
        )
        assert screen._get_log_path("stdout") == "/path/to/out.log"

    def test_get_log_path_stderr(self, mock_job, mock_ssh_client):
        screen = JobDetailScreen(mock_job, mock_ssh_client)
        screen.details = JobDetails(
            stdout_path="/path/to/out.log",
            stderr_path="/path/to/err.log",
        )
        assert screen._get_log_path("stderr") == "/path/to/err.log"

    def test_get_log_path_no_details(self, mock_job, mock_ssh_client):
        screen = JobDetailScreen(mock_job, mock_ssh_client)
        assert screen._get_log_path("stdout") is None
        assert screen._get_log_path("stderr") is None

    def test_get_log_path_empty_path(self, mock_job, mock_ssh_client):
        screen = JobDetailScreen(mock_job, mock_ssh_client)
        screen.details = JobDetails(stdout_path="", stderr_path="")
        assert screen._get_log_path("stdout") is None
        assert screen._get_log_path("stderr") is None

    def test_has_requeue_hold_release_bindings(self):
        keys = {b.key for b in JobDetailScreen.BINDINGS}
        assert "r" in keys
        assert "h" in keys
        assert "l" in keys

    def test_action_hold_and_release_dispatch_commands(self, mock_job, mock_ssh_client):
        screen = JobDetailScreen(mock_job, mock_ssh_client)
        with patch.object(screen, "_run_job_command") as run:
            screen.action_hold_job()
            run.assert_called_with(mock_job, "scontrol hold", "Held")

            screen.action_release_job()
            run.assert_called_with(mock_job, "scontrol release", "Released")

    def test_do_requeue_dispatches_when_confirmed(self, mock_job, mock_ssh_client):
        screen = JobDetailScreen(mock_job, mock_ssh_client)
        with patch.object(screen, "_run_job_command") as run:
            screen._do_requeue(mock_job, True)
            run.assert_called_once_with(mock_job, "scontrol requeue", "Requeued")

    def test_do_requeue_skips_when_not_confirmed(self, mock_job, mock_ssh_client):
        screen = JobDetailScreen(mock_job, mock_ssh_client)
        with patch.object(screen, "_run_job_command") as run:
            screen._do_requeue(mock_job, False)
            run.assert_not_called()

    def test_run_job_command_executes_and_notifies_success(
        self, mock_job, mock_ssh_client
    ):
        screen = JobDetailScreen(mock_job, mock_ssh_client)
        mock_app = MagicMock()
        mock_app.call_from_thread = lambda fn, *a, **k: fn(*a, **k)
        with (
            patch.object(mock_ssh_client, "execute", return_value="") as execute,
            patch.object(
                type(screen), "app", new_callable=lambda: property(lambda _s: mock_app)
            ),
            patch.object(screen, "notify") as notify,
            patch.object(screen, "run_worker", side_effect=lambda fn, **kwargs: fn()),
        ):
            screen._run_job_command(mock_job, "scontrol hold", "Held")

        execute.assert_called_once_with("scontrol hold 12345", timeout=10)
        notify.assert_called_with("Held job 12345", timeout=3)


class TestJobDetailScreenFavourites:
    def _db(self):
        from slurmhub.db.engine import Database, _run_migrations, make_engine

        engine = make_engine("sqlite://", in_memory=True)
        _run_migrations(engine)
        return Database(engine)

    def test_defaults_to_no_persistence(self, mock_job, mock_ssh_client):
        screen = JobDetailScreen(mock_job, mock_ssh_client)
        assert screen.repository is None
        assert screen.database is None
        assert screen._favourite is False

    def test_has_favourite_and_note_bindings(self):
        keys = {b.key for b in JobDetailScreen.BINDINGS}
        assert "f" in keys
        assert "n" in keys

    def test_submit_time_prefers_details(self, mock_job, mock_ssh_client):
        screen = JobDetailScreen(mock_job, mock_ssh_client)
        screen.details = JobDetails(submit_time="2026-01-01T00:00:00")
        assert screen._submit_time() == "2026-01-01T00:00:00"

    def test_load_favourite_state_reads_repository(self, mock_job, mock_ssh_client):
        from slurmhub.db.repository import Repository

        db = self._db()
        repo = Repository()
        mock_job.submit_time = "2026-01-01T00:00:00"
        with db.session() as s:
            pk = repo.upsert_job(s, "p1", mock_job)
            repo.set_favourite(s, pk, True, note="hi")
        screen = JobDetailScreen(
            mock_job,
            mock_ssh_client,
            repository=repo,
            database=db,
            profile_name="p1",
        )
        screen._load_favourite_state()
        assert screen._favourite is True
        assert screen._note == "hi"
        db.close()
