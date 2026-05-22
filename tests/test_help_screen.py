"""Tests for the modal help cheatsheet screen."""

import pytest

from slurm_monitor.app import SlurmMonitorApp
from slurm_monitor.config import AppConfig, LogConfig, ProfileConfig, SSHConfig
from slurm_monitor.widgets.help_screen import HelpScreen


def _single_profile_config() -> AppConfig:
    return AppConfig(
        profiles={
            "clusterA": ProfileConfig(ssh=SSHConfig(host="host1"), log=LogConfig()),
        }
    )


class TestHelpScreenContent:
    """The help screen renders one of the known contexts."""

    def test_unknown_context_falls_back_to_main(self):
        screen = HelpScreen(context="nonexistent")
        assert screen.context == "main"

    def test_each_context_has_at_least_one_section(self):
        for ctx in ("main", "detail", "dashboard", "log"):
            screen = HelpScreen(context=ctx)
            body = str(screen._render_body())
            assert "Esc" in body or "q" in body or "/" in body, (
                f"context={ctx}: expected at least one keybinding in the body"
            )


class TestHelpScreenWiring:
    """? on the main app pushes the help screen; Esc dismisses it."""

    @pytest.mark.asyncio
    async def test_question_mark_opens_help_from_main(self):
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            await pilot.press("question_mark")
            await pilot.pause()
            assert isinstance(app.screen, HelpScreen)
            assert app.screen.context == "main"

    @pytest.mark.asyncio
    async def test_escape_dismisses_help_from_main(self):
        app = SlurmMonitorApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            await pilot.press("question_mark")
            await pilot.pause()
            assert isinstance(app.screen, HelpScreen)

            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, HelpScreen)
