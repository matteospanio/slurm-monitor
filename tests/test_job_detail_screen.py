"""Tests for the JobDetailScreen widget."""

from unittest.mock import MagicMock, patch

import pytest

from slurmhub.config import SSHConfig
from slurmhub.scontrol_parser import JobDetails
from slurmhub.squeue_parser import SlurmJob
from slurmhub.ssh_wrapper import SSHClient
from slurmhub.widgets.job_detail_screen import JobDetailScreen


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
