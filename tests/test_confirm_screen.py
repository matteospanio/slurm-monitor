"""Tests for the generic ConfirmScreen modal."""

import pytest
from textual.app import App, ComposeResult

from slurm_monitor.widgets.confirm_screen import ConfirmScreen


class _Host(App):
    """Minimal App for pushing ConfirmScreen."""

    last_result = None

    def compose(self) -> ComposeResult:
        return []


class TestConfirmScreen:
    @pytest.mark.asyncio
    async def test_y_dismisses_with_true(self):
        app = _Host()
        async with app.run_test() as pilot:
            def _record(value):
                app.last_result = value

            app.push_screen(ConfirmScreen("Cancel?"), callback=_record)
            await pilot.pause()
            assert isinstance(app.screen, ConfirmScreen)

            await pilot.press("y")
            await pilot.pause()
            assert app.last_result is True

    @pytest.mark.asyncio
    async def test_n_dismisses_with_false(self):
        app = _Host()
        async with app.run_test() as pilot:
            def _record(value):
                app.last_result = value

            app.push_screen(ConfirmScreen("Cancel?"), callback=_record)
            await pilot.pause()

            await pilot.press("n")
            await pilot.pause()
            assert app.last_result is False

    @pytest.mark.asyncio
    async def test_escape_dismisses_with_false(self):
        app = _Host()
        async with app.run_test() as pilot:
            def _record(value):
                app.last_result = value

            app.push_screen(ConfirmScreen("Cancel?"), callback=_record)
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()
            assert app.last_result is False
