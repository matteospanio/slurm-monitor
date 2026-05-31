"""Pilot tests for the HistoryScreen and the H keybinding."""

import pytest
from textual.widgets import DataTable

from slurmhub.app import SlurmhubApp
from slurmhub.config import AppConfig, ProfileConfig, SSHConfig
from slurmhub.db.engine import open_demo_database
from slurmhub.demo_data import DEMO_HOST, DEMO_USERNAME
from slurmhub.widgets.history_screen import HistoryScreen
from slurmhub.widgets.note_input_screen import NoteInputScreen


def _demo_config() -> AppConfig:
    profile = ProfileConfig(
        name="demo", ssh=SSHConfig(host=DEMO_HOST, username=DEMO_USERNAME)
    )
    return AppConfig(profiles={"demo": profile})


def _demo_app() -> SlurmhubApp:
    return SlurmhubApp(config=_demo_config(), demo=True, database=open_demo_database())


class TestHistoryKeybinding:
    @pytest.mark.asyncio
    async def test_h_opens_history(self):
        app = _demo_app()
        async with app.run_test() as pilot:
            await pilot.press("H")
            await pilot.pause(0.4)
            assert isinstance(app.screen, HistoryScreen)
            table = app.screen.query_one("#history-table", DataTable)
            assert table.row_count > 0

    @pytest.mark.asyncio
    async def test_escape_closes_history(self):
        app = _demo_app()
        async with app.run_test() as pilot:
            await pilot.press("H")
            await pilot.pause(0.3)
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, HistoryScreen)

    @pytest.mark.asyncio
    async def test_h_disabled_when_no_database(self):
        app = SlurmhubApp(config=_demo_config(), demo=True, database=None)
        async with app.run_test() as pilot:
            await pilot.press("H")
            await pilot.pause()
            assert not isinstance(app.screen, HistoryScreen)


class TestHistoryScreenInteractions:
    @pytest.mark.asyncio
    async def test_aggregates_toggle(self):
        app = _demo_app()
        async with app.run_test() as pilot:
            await pilot.press("H")
            await pilot.pause(0.4)
            screen = app.screen
            assert screen.mode == "list"
            await pilot.press("a")
            await pilot.pause()
            assert screen.mode == "aggregates"
            assert not screen.query_one("#history-table", DataTable).display

    @pytest.mark.asyncio
    async def test_favourites_only_filter(self):
        app = _demo_app()
        async with app.run_test() as pilot:
            await pilot.press("H")
            await pilot.pause(0.4)
            screen = app.screen
            total = screen.query_one("#history-table", DataTable).row_count
            await pilot.press("F")  # favourites-only
            await pilot.pause(0.3)
            fav_rows = screen.query_one("#history-table", DataTable).row_count
            assert 0 < fav_rows < total

    @pytest.mark.asyncio
    async def test_state_filter_completed(self):
        app = _demo_app()
        async with app.run_test() as pilot:
            await pilot.press("H")
            await pilot.pause(0.4)
            screen = app.screen
            await pilot.press("3")  # COMPLETED
            await pilot.pause(0.3)
            assert screen.state_label == "COMPLETED"
            for run in screen.runs:
                assert run.state == "COMPLETED"

    @pytest.mark.asyncio
    async def test_toggle_favourite_on_row(self):
        app = _demo_app()
        async with app.run_test() as pilot:
            await pilot.press("H")
            await pilot.pause(0.4)
            screen = app.screen
            run = screen.runs[0]
            was_fav = run.favourite
            await pilot.press("f")
            await pilot.pause(0.4)
            # Re-query reflects the flip for the same run.
            flipped = next((r for r in screen.runs if r.pk == run.pk), None)
            assert flipped is not None
            assert flipped.favourite is (not was_fav)

    @pytest.mark.asyncio
    async def test_note_opens_modal(self):
        app = _demo_app()
        async with app.run_test() as pilot:
            await pilot.press("H")
            await pilot.pause(0.4)
            await pilot.press("n")
            await pilot.pause()
            assert isinstance(app.screen, NoteInputScreen)
