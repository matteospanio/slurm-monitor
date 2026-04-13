"""Tests for the JobTable widget helpers and cursor preservation."""

import pytest

from textual.app import App, ComposeResult

from slurm_monitor.squeue_parser import SlurmJob
from slurm_monitor.widgets.job_table import JobTable, _truncate_path


def _make_job(job_id: str, name: str = "test", state: str = "RUNNING") -> SlurmJob:
    return SlurmJob(job_id=job_id, name=name, state=state, time="00:10:00")


class _JobTableApp(App):
    """Minimal app for testing JobTable."""

    def compose(self) -> ComposeResult:
        yield JobTable(id="table")


class TestTruncatePath:
    def test_long_path(self):
        assert _truncate_path("/home/user/projects/ml/train") == "../ml/train"

    def test_three_components(self):
        # /home/user has parts ('/', 'home', 'user') = 3 parts, truncated to last 2
        assert _truncate_path("/home/user") == "../home/user"

    def test_single_component(self):
        assert _truncate_path("/home") == "/home"

    def test_empty_string(self):
        assert _truncate_path("") == ""

    def test_custom_components(self):
        assert _truncate_path("/a/b/c/d/e", components=3) == "../c/d/e"

    def test_keeps_last_two_dirs(self):
        assert _truncate_path("/home/spanio/jobs/tmp/mxlGPT") == "../tmp/mxlGPT"


class TestCursorPreservation:
    """Cursor should stay on the same job across update_jobs() calls."""

    @pytest.mark.asyncio
    async def test_cursor_stays_on_same_job(self):
        """After refresh with same jobs, cursor stays on the selected job."""
        jobs = [_make_job("3"), _make_job("2"), _make_job("1")]

        async with _JobTableApp().run_test() as pilot:
            table = pilot.app.query_one("#table", JobTable)
            table.update_jobs(jobs)

            # Move cursor to row 2 (job_id "1")
            table.move_cursor(row=2)
            assert table.cursor_row == 2

            # Refresh with same jobs
            table.update_jobs(jobs)
            assert table.cursor_row == 2

    @pytest.mark.asyncio
    async def test_cursor_follows_job_when_reordered(self):
        """If job moves to a different row, cursor follows it."""
        jobs_v1 = [_make_job("3"), _make_job("2"), _make_job("1")]
        jobs_v2 = [_make_job("2"), _make_job("3"), _make_job("1")]

        async with _JobTableApp().run_test() as pilot:
            table = pilot.app.query_one("#table", JobTable)
            table.update_jobs(jobs_v1)

            # Select job_id "2" (row 1)
            table.move_cursor(row=1)
            assert table.cursor_row == 1

            # Refresh with reordered jobs — "2" is now row 0
            table.update_jobs(jobs_v2)
            assert table.cursor_row == 0

    @pytest.mark.asyncio
    async def test_cursor_clamps_when_job_disappears(self):
        """If selected job disappears, cursor clamps to nearest valid row."""
        jobs_v1 = [_make_job("3"), _make_job("2"), _make_job("1")]
        jobs_v2 = [_make_job("3"), _make_job("1")]

        async with _JobTableApp().run_test() as pilot:
            table = pilot.app.query_one("#table", JobTable)
            table.update_jobs(jobs_v1)

            # Select job_id "2" (row 1)
            table.move_cursor(row=1)
            assert table.cursor_row == 1

            # Refresh without job "2" — cursor should clamp to row 1 (last valid)
            table.update_jobs(jobs_v2)
            assert table.cursor_row == 1

    @pytest.mark.asyncio
    async def test_cursor_clamps_when_job_disappears_from_end(self):
        """If cursor was on last row and it disappears, clamp to new last row."""
        jobs_v1 = [_make_job("3"), _make_job("2"), _make_job("1")]
        jobs_v2 = [_make_job("3")]

        async with _JobTableApp().run_test() as pilot:
            table = pilot.app.query_one("#table", JobTable)
            table.update_jobs(jobs_v1)

            # Select last row (job_id "1", row 2)
            table.move_cursor(row=2)

            # Refresh with only 1 job — cursor clamps to row 0
            table.update_jobs(jobs_v2)
            assert table.cursor_row == 0

    @pytest.mark.asyncio
    async def test_empty_refresh_no_crash(self):
        """Refreshing with empty job list does not crash."""
        jobs = [_make_job("1")]

        async with _JobTableApp().run_test() as pilot:
            table = pilot.app.query_one("#table", JobTable)
            table.update_jobs(jobs)
            table.move_cursor(row=0)

            # Refresh with empty list
            table.update_jobs([])
            assert table.row_count == 0

    @pytest.mark.asyncio
    async def test_first_populate_cursor_at_zero(self):
        """First population starts cursor at row 0."""
        jobs = [_make_job("3"), _make_job("2"), _make_job("1")]

        async with _JobTableApp().run_test() as pilot:
            table = pilot.app.query_one("#table", JobTable)
            table.update_jobs(jobs)
            assert table.cursor_row == 0

    @pytest.mark.asyncio
    async def test_new_job_inserted_cursor_follows(self):
        """When a new job is inserted before the selected one, cursor follows."""
        jobs_v1 = [_make_job("3"), _make_job("1")]
        jobs_v2 = [_make_job("3"), _make_job("2"), _make_job("1")]

        async with _JobTableApp().run_test() as pilot:
            table = pilot.app.query_one("#table", JobTable)
            table.update_jobs(jobs_v1)

            # Select job_id "1" (row 1)
            table.move_cursor(row=1)

            # New job "2" inserted — "1" shifts to row 2
            table.update_jobs(jobs_v2)
            assert table.cursor_row == 2
