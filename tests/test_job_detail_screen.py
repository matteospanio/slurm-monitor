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
            mock_job, mock_ssh_client, repository=repo, database=db,
            profile_name="p1",
        )
        screen._load_favourite_state()
        assert screen._favourite is True
        assert screen._note == "hi"
        db.close()
