"""Tests for the NoteInputScreen modal."""

import pytest
from textual.app import App, ComposeResult

from slurmhub.widgets.note_input_screen import NoteInputScreen


class _Host(App):
    """Minimal host that pushes a NoteInputScreen and captures its result."""

    def __init__(self, screen: NoteInputScreen) -> None:
        super().__init__()
        self._screen = screen
        self.result = "UNSET"

    def compose(self) -> ComposeResult:
        return []

    def on_mount(self) -> None:
        self.push_screen(self._screen, callback=self._cb)

    def _cb(self, value) -> None:
        self.result = value


class TestNoteInputScreenConstruction:
    def test_stores_job_id_and_initial(self):
        screen = NoteInputScreen("12345", initial="hello")
        assert screen.job_id == "12345"
        assert screen.initial == "hello"

    def test_is_modal(self):
        from textual.screen import ModalScreen

        assert isinstance(NoteInputScreen("1"), ModalScreen)


class TestNoteInputScreenPilot:
    @pytest.mark.asyncio
    async def test_submit_returns_value(self):
        app = _Host(NoteInputScreen("1", initial="baseline"))
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
        assert app.result == "baseline"

    @pytest.mark.asyncio
    async def test_empty_submit_clears_note(self):
        app = _Host(NoteInputScreen("1", initial=""))
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
        assert app.result == ""

    @pytest.mark.asyncio
    async def test_escape_returns_none(self):
        app = _Host(NoteInputScreen("1", initial="x"))
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        assert app.result is None
