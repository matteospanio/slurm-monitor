"""Tests for the main TUI application logic."""

from unittest.mock import MagicMock, patch

import pytest

from slurm_monitor.app import ProfileTab, SlurmMonitorApp
from slurm_monitor.config import AppConfig, ProfileConfig, SSHConfig, LogConfig
from slurm_monitor.ssh_wrapper import SSHConnectionError, SSHTimeoutError


@pytest.fixture
def app_config():
    profile = ProfileConfig(
        ssh=SSHConfig(host="testhost"),
        log=LogConfig(),
    )
    return AppConfig(profiles={"test": profile})


@pytest.fixture
def app(app_config):
    return SlurmMonitorApp(config=app_config)


class TestFetchJobsErrorHandling:
    """Test that _fetch_jobs handles SSH errors gracefully."""

    def test_ssh_connection_error_returns_empty_jobs(self, app):
        tab = app._profile_tabs["test"]

        with patch(
            "slurm_monitor.squeue_parser.fetch_squeue_jobs",
            side_effect=SSHConnectionError("Connection refused"),
        ):
            profile_name, jobs, error = app._fetch_jobs(tab, "test")

        assert profile_name == "test"
        assert jobs == []
        assert "Connection refused" in str(error)

    def test_ssh_timeout_error_returns_empty_jobs(self, app):
        tab = app._profile_tabs["test"]

        with patch(
            "slurm_monitor.squeue_parser.fetch_squeue_jobs",
            side_effect=SSHTimeoutError("Timed out"),
        ):
            profile_name, jobs, error = app._fetch_jobs(tab, "test")

        assert profile_name == "test"
        assert jobs == []
        assert "Timed out" in str(error)

    def test_successful_fetch_returns_no_error(self, app):
        tab = app._profile_tabs["test"]

        with patch(
            "slurm_monitor.squeue_parser.fetch_squeue_jobs", return_value=[]
        ), patch(
            "slurm_monitor.sacct_parser.fetch_sacct_jobs", return_value=[]
        ):
            profile_name, jobs, error = app._fetch_jobs(tab, "test")

        assert profile_name == "test"
        assert jobs == []
        assert error is None

    def test_sacct_connection_error_returns_empty_jobs(self, app):
        """SSH error during sacct fetch is also handled."""
        tab = app._profile_tabs["test"]
        tab._sacct_last_fetch = 0.0  # force sacct re-fetch

        with patch(
            "slurm_monitor.squeue_parser.fetch_squeue_jobs", return_value=[]
        ), patch(
            "slurm_monitor.sacct_parser.fetch_sacct_jobs",
            side_effect=SSHConnectionError("Connection lost"),
        ):
            profile_name, jobs, error = app._fetch_jobs(tab, "test")

        assert profile_name == "test"
        assert jobs == []
        assert "Connection lost" in str(error)
