"""Tests for the main TUI application logic."""

from unittest.mock import MagicMock, patch

import pytest

from slurm_monitor.app import FetchResult, ProfileTab, SlurmMonitorApp
from slurm_monitor.config import AppConfig, ProfileConfig, SSHConfig, LogConfig
from slurm_monitor.squeue_parser import SlurmJob
from slurm_monitor.ssh_wrapper import SSHConnectionError, SSHTimeoutError
from slurm_monitor.widgets.job_table import JobTable


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
            result = app._fetch_jobs(tab, "test")

        assert result.profile_name == "test"
        assert result.jobs == []
        assert "Connection refused" in str(result.error)

    def test_ssh_timeout_error_returns_empty_jobs(self, app):
        tab = app._profile_tabs["test"]

        with patch(
            "slurm_monitor.squeue_parser.fetch_squeue_jobs",
            side_effect=SSHTimeoutError("Timed out"),
        ):
            result = app._fetch_jobs(tab, "test")

        assert result.profile_name == "test"
        assert result.jobs == []
        assert "Timed out" in str(result.error)

    def test_successful_fetch_returns_no_error(self, app):
        tab = app._profile_tabs["test"]

        with patch(
            "slurm_monitor.squeue_parser.fetch_squeue_jobs", return_value=[]
        ), patch(
            "slurm_monitor.sacct_parser.fetch_sacct_jobs", return_value=[]
        ):
            result = app._fetch_jobs(tab, "test")

        assert result.profile_name == "test"
        assert result.jobs == []
        assert result.error is None

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
            result = app._fetch_jobs(tab, "test")

        assert result.profile_name == "test"
        assert result.jobs == []
        assert "Connection lost" in str(result.error)


def _make_job(job_id: str, name: str = "job") -> SlurmJob:
    return SlurmJob(job_id=job_id, name=name, state="RUNNING", time="00:01:00")


def _single_profile_config() -> AppConfig:
    profile = ProfileConfig(ssh=SSHConfig(host="host1"), log=LogConfig())
    return AppConfig(profiles={"clusterA": profile})


def _multi_profile_config() -> AppConfig:
    a = ProfileConfig(ssh=SSHConfig(host="host1"), log=LogConfig())
    b = ProfileConfig(ssh=SSHConfig(host="host2"), log=LogConfig())
    c = ProfileConfig(ssh=SSHConfig(host="host3"), log=LogConfig())
    return AppConfig(profiles={"alpha": a, "beta": b, "gamma": c})


class TestVimNavigation:
    """g/G move the cursor to top/bottom, h/l switch tabs."""

    @pytest.mark.asyncio
    async def test_g_moves_cursor_to_first_row(self):
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            tab = app._profile_tabs["clusterA"]
            tab.jobs = [_make_job(str(i)) for i in range(5)]
            app._update_display("clusterA")
            await pilot.pause()

            table = app.query_one("#table-clusterA", JobTable)
            table.move_cursor(row=4)
            assert table.cursor_row == 4

            await pilot.press("g")
            assert table.cursor_row == 0

    @pytest.mark.asyncio
    async def test_shift_g_moves_cursor_to_last_row(self):
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            tab = app._profile_tabs["clusterA"]
            tab.jobs = [_make_job(str(i)) for i in range(5)]
            app._update_display("clusterA")
            await pilot.pause()

            table = app.query_one("#table-clusterA", JobTable)
            table.move_cursor(row=0)
            assert table.cursor_row == 0

            await pilot.press("shift+g")
            assert table.cursor_row == 4

    @pytest.mark.asyncio
    async def test_j_k_move_cursor_one_row(self):
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            tab = app._profile_tabs["clusterA"]
            tab.jobs = [_make_job(str(i)) for i in range(3)]
            app._update_display("clusterA")
            await pilot.pause()

            table = app.query_one("#table-clusterA", JobTable)
            table.move_cursor(row=0)

            await pilot.press("j")
            assert table.cursor_row == 1

            await pilot.press("j")
            assert table.cursor_row == 2

            await pilot.press("k")
            assert table.cursor_row == 1

    @pytest.mark.asyncio
    async def test_g_with_empty_table_does_not_crash(self):
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            await pilot.press("g")
            await pilot.press("shift+g")

    @pytest.mark.asyncio
    async def test_l_switches_to_next_tab(self):
        app = SlurmMonitorApp(config=_multi_profile_config())
        async with app.run_test() as pilot:
            assert app._get_active_profile_name() == "alpha"

            await pilot.press("l")
            assert app._get_active_profile_name() == "beta"

            await pilot.press("l")
            assert app._get_active_profile_name() == "gamma"

            # wraps around
            await pilot.press("l")
            assert app._get_active_profile_name() == "alpha"

    @pytest.mark.asyncio
    async def test_h_switches_to_previous_tab(self):
        app = SlurmMonitorApp(config=_multi_profile_config())
        async with app.run_test() as pilot:
            assert app._get_active_profile_name() == "alpha"

            # wraps backwards
            await pilot.press("h")
            assert app._get_active_profile_name() == "gamma"

            await pilot.press("h")
            assert app._get_active_profile_name() == "beta"

            await pilot.press("h")
            assert app._get_active_profile_name() == "alpha"

    @pytest.mark.asyncio
    async def test_h_l_no_op_with_single_profile(self):
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            assert app._get_active_profile_name() == "clusterA"
            await pilot.press("l")
            assert app._get_active_profile_name() == "clusterA"
            await pilot.press("h")
            assert app._get_active_profile_name() == "clusterA"
