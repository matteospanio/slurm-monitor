"""Tests for the main TUI application logic."""

from unittest.mock import MagicMock, patch

import pytest

from slurm_monitor.app import FetchResult, ProfileTab, SlurmMonitorApp
from slurm_monitor.config import AppConfig, ProfileConfig, SSHConfig, LogConfig
from slurm_monitor.squeue_parser import SlurmJob
from slurm_monitor.ssh_wrapper import SSHConnectionError, SSHTimeoutError
from slurm_monitor.widgets.job_detail import JobDetail
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
        """Real terminals deliver Shift+G as the literal "G" key — the
        binding must match that form, not just "shift+g"."""
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            tab = app._profile_tabs["clusterA"]
            tab.jobs = [_make_job(str(i)) for i in range(5)]
            app._update_display("clusterA")
            await pilot.pause()

            table = app.query_one("#table-clusterA", JobTable)
            table.move_cursor(row=0)
            assert table.cursor_row == 0

            # Press the literal "G" — what the xterm parser produces for
            # Shift+G on a real terminal.
            await pilot.press("G")
            assert table.cursor_row == 4

    @pytest.mark.asyncio
    async def test_shift_plus_g_alias_also_works(self):
        """The synthetic "shift+g" form should also map to scroll_bottom."""
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            tab = app._profile_tabs["clusterA"]
            tab.jobs = [_make_job(str(i)) for i in range(5)]
            app._update_display("clusterA")
            await pilot.pause()

            table = app.query_one("#table-clusterA", JobTable)
            table.move_cursor(row=0)
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
            await pilot.press("G")

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
    async def test_detail_panel_populated_on_initial_render(self):
        """Detail panel should show the row-0 job even without cursor move."""
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            tab = app._profile_tabs["clusterA"]
            tab.jobs = [_make_job("42", name="alpha"), _make_job("43")]
            app._update_display("clusterA")
            await pilot.pause()

            detail = app.query_one("#detail-clusterA", JobDetail)
            # The widget renders Rich Text — check internal state instead.
            assert detail._job is not None
            assert detail._job.job_id == "42"

    @pytest.mark.asyncio
    async def test_detail_panel_shows_empty_message_when_no_jobs(self):
        """With no jobs, the panel should reflect that, not 'No job selected'."""
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            tab = app._profile_tabs["clusterA"]
            tab.jobs = []
            app._update_display("clusterA")
            await pilot.pause()

            detail = app.query_one("#detail-clusterA", JobDetail)
            assert detail._job is None
            assert detail._has_jobs is False
            rendered = str(detail.render())
            assert "No jobs to display" in rendered

    @pytest.mark.asyncio
    async def test_h_l_no_op_with_single_profile(self):
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            assert app._get_active_profile_name() == "clusterA"
            await pilot.press("l")
            assert app._get_active_profile_name() == "clusterA"
            await pilot.press("h")
            assert app._get_active_profile_name() == "clusterA"


class TestScancelAction:
    """`c` opens the confirm modal; only on `y` is scancel actually sent."""

    @pytest.mark.asyncio
    async def test_c_with_no_jobs_notifies(self):
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            tab = app._profile_tabs["clusterA"]
            tab.jobs = []
            app._update_display("clusterA")
            await pilot.pause()

            # No SSH should be touched.
            with patch.object(tab.ssh_client, "execute") as mock_exec:
                await pilot.press("c")
                await pilot.pause()
                mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_c_opens_confirm_screen(self):
        from slurm_monitor.widgets.confirm_screen import ConfirmScreen

        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            tab = app._profile_tabs["clusterA"]
            tab.jobs = [_make_job("100")]
            app._update_display("clusterA")
            await pilot.pause()

            await pilot.press("c")
            await pilot.pause()
            assert isinstance(app.screen, ConfirmScreen)

    @pytest.mark.asyncio
    async def test_c_y_triggers_scancel(self):
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            tab = app._profile_tabs["clusterA"]
            tab.jobs = [_make_job("100")]
            app._update_display("clusterA")
            await pilot.pause()

            with patch.object(
                tab.ssh_client, "execute", return_value=""
            ) as mock_exec:
                await pilot.press("c")
                await pilot.pause()
                await pilot.press("y")
                await pilot.pause(0.3)  # let the worker run

                # First positional arg should be "scancel 100"
                calls = [c for c in mock_exec.call_args_list]
                assert any(
                    "scancel" in c.args[0] and "100" in c.args[0]
                    for c in calls
                )

    @pytest.mark.asyncio
    async def test_c_n_does_not_call_scancel(self):
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            tab = app._profile_tabs["clusterA"]
            tab.jobs = [_make_job("100")]
            app._update_display("clusterA")
            await pilot.pause()

            with patch.object(tab.ssh_client, "execute") as mock_exec:
                await pilot.press("c")
                await pilot.pause()
                await pilot.press("n")
                await pilot.pause()
                mock_exec.assert_not_called()


class TestPartialFetchErrors:
    """Sub-fetch failures (sinfo / queue_stats / pending_details) are
    captured into FetchResult.partial_errors and surfaced as warnings
    without breaking the main fetch."""

    def test_sinfo_failure_recorded_in_partial_errors(self, app):
        tab = app._profile_tabs["test"]
        tab._sinfo_last_fetch = 0.0  # force a sinfo fetch attempt

        with patch(
            "slurm_monitor.squeue_parser.fetch_squeue_jobs", return_value=[]
        ), patch(
            "slurm_monitor.sacct_parser.fetch_sacct_jobs", return_value=[]
        ), patch(
            "slurm_monitor.app.fetch_sinfo",
            side_effect=RuntimeError("sinfo unavailable"),
        ):
            result = app._fetch_jobs(tab, "test")

        assert result.error is None
        assert "sinfo" in result.partial_errors
        assert "sinfo unavailable" in result.partial_errors["sinfo"]

    def test_queue_stats_failure_isolated(self, app):
        tab = app._profile_tabs["test"]
        tab._queue_stats_last_fetch = 0.0

        with patch(
            "slurm_monitor.squeue_parser.fetch_squeue_jobs", return_value=[]
        ), patch(
            "slurm_monitor.sacct_parser.fetch_sacct_jobs", return_value=[]
        ), patch(
            "slurm_monitor.app.fetch_cluster_queue_stats",
            side_effect=RuntimeError("network blip"),
        ):
            result = app._fetch_jobs(tab, "test")

        assert result.error is None
        assert "queue_stats" in result.partial_errors


class TestFilterBarUX:
    """Escape closes the filter bar and clears the search."""

    @pytest.mark.asyncio
    async def test_slash_then_escape_clears_filter(self):
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            from slurm_monitor.widgets.filter_bar import FilterBar
            from textual.widgets import Input

            await pilot.press("slash")
            await pilot.pause()
            filter_bar = app.query_one("#filter-bar", FilterBar)
            assert filter_bar.display is True

            inp = filter_bar.query_one(Input)
            inp.value = "training"
            await pilot.pause()

            tab = app._profile_tabs["clusterA"]
            assert tab.name_filter == "training"

            await pilot.press("escape")
            await pilot.pause()

            assert filter_bar.display is False
            assert tab.name_filter == ""

    @pytest.mark.asyncio
    async def test_status_bar_shows_visible_count_when_filtered(self):
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            tab = app._profile_tabs["clusterA"]
            tab.jobs = [
                _make_job("1"),
                _make_job("2"),
                _make_job("3"),
            ]
            tab.jobs[1].state = "PENDING"
            tab.state_filter = "RUNNING"
            app._update_display("clusterA")
            await pilot.pause()

            from slurm_monitor.widgets.status_bar import StatusBar
            sb = app.query_one("#status-bar", StatusBar)
            rendered = str(sb.render())
            assert "2 of 3 shown" in rendered


class TestPerTabFilterIsolation:
    """Filter / search / sort state should be remembered per profile tab."""

    @pytest.mark.asyncio
    async def test_state_filter_isolated_per_tab(self):
        app = SlurmMonitorApp(config=_multi_profile_config())
        async with app.run_test() as pilot:
            # Start on alpha; press 1 to filter RUNNING
            assert app._get_active_profile_name() == "alpha"
            await pilot.press("1")
            assert app._profile_tabs["alpha"].state_filter == "RUNNING"

            # Switch to beta — its filter should still be ALL
            await pilot.press("l")
            assert app._get_active_profile_name() == "beta"
            assert app._profile_tabs["beta"].state_filter == "ALL"

            # Set beta to PENDING
            await pilot.press("2")
            assert app._profile_tabs["beta"].state_filter == "PENDING"

            # Switch back to alpha — RUNNING preserved
            await pilot.press("h")
            assert app._get_active_profile_name() == "alpha"
            assert app._profile_tabs["alpha"].state_filter == "RUNNING"
            # beta still PENDING
            assert app._profile_tabs["beta"].state_filter == "PENDING"

    @pytest.mark.asyncio
    async def test_sort_mode_isolated_per_tab(self):
        app = SlurmMonitorApp(config=_multi_profile_config())
        async with app.run_test() as pilot:
            await pilot.press("s")  # alpha → time
            assert app._profile_tabs["alpha"].sort_mode == "time"

            await pilot.press("l")  # → beta, still default
            assert app._profile_tabs["beta"].sort_mode == "id"

            await pilot.press("s")  # beta → time
            await pilot.press("s")  # beta → name
            assert app._profile_tabs["beta"].sort_mode == "name"

            await pilot.press("h")  # back to alpha
            assert app._profile_tabs["alpha"].sort_mode == "time"

    @pytest.mark.asyncio
    async def test_name_filter_isolated_per_tab(self):
        app = SlurmMonitorApp(config=_multi_profile_config())
        async with app.run_test() as pilot:
            app._profile_tabs["alpha"].name_filter = "training"
            app._profile_tabs["beta"].name_filter = ""

            # Switching tabs should reflect the active tab's filter
            await pilot.press("l")
            assert app._get_active_profile_name() == "beta"
            filter_bar = app.query_one("#filter-bar")
            from textual.widgets import Input
            assert filter_bar.query_one(Input).value == ""

            await pilot.press("h")
            assert app._get_active_profile_name() == "alpha"
            assert filter_bar.query_one(Input).value == "training"


class TestDetailPanelToggle:
    """Capital D hides / shows the JobDetail bottom panel."""

    @pytest.mark.asyncio
    async def test_shift_d_toggles_detail_panel(self):
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            detail = app.query_one("#detail-clusterA", JobDetail)
            assert detail.display is True

            await pilot.press("D")
            assert detail.display is False

            await pilot.press("D")
            assert detail.display is True

    @pytest.mark.asyncio
    async def test_shift_plus_d_alias_also_toggles(self):
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            detail = app.query_one("#detail-clusterA", JobDetail)
            await pilot.press("shift+d")
            assert detail.display is False
