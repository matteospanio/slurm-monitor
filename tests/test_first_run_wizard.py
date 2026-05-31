"""Tests for the FirstRunWizardScreen and its helpers."""

import getpass
import os
from unittest.mock import patch

import pytest

from textual.app import App, ComposeResult
from textual.widgets import Input, Static

from slurmhub.config import ProfileConfig
from slurmhub.tui.widgets.first_run_wizard import (
    ConfirmScreen,
    FirstRunWizardScreen,
    _default_key_path,
    build_profile_from_fields,
)


class TestBuildProfileFromFields:
    def test_happy_path(self):
        profile, err = build_profile_from_fields(
            name="dei",
            host="login.dei.unipd.it",
            username="matteo",
            port="22",
            key_filename="~/.ssh/id_ed25519",
            log_pattern="{work_dir}/logs/{job_id}.out",
        )
        assert err is None
        assert isinstance(profile, ProfileConfig)
        assert profile.name == "dei"
        assert profile.ssh.host == "login.dei.unipd.it"
        assert profile.ssh.port == 22
        assert profile.ssh.username == "matteo"
        # ~ should be expanded to an absolute path
        assert profile.ssh.key_filename == os.path.expanduser("~/.ssh/id_ed25519")
        assert profile.log.default_pattern == "{work_dir}/logs/{job_id}.out"

    def test_missing_host_returns_error(self):
        profile, err = build_profile_from_fields(
            name="x", host="", username="me", port="22",
            key_filename="", log_pattern="",
        )
        assert profile is None
        assert err is not None and "host" in err.lower()

    def test_invalid_port_returns_error(self):
        profile, err = build_profile_from_fields(
            name="x", host="cluster", username="me", port="not-a-number",
            key_filename="", log_pattern="",
        )
        assert profile is None
        assert err is not None and "port" in err.lower()

    def test_empty_name_defaults(self):
        profile, _ = build_profile_from_fields(
            name="", host="cluster", username="me", port="22",
            key_filename="", log_pattern="",
        )
        assert profile is not None
        assert profile.name == "default"

    def test_empty_log_pattern_uses_default(self):
        profile, _ = build_profile_from_fields(
            name="x", host="cluster", username="me", port="22",
            key_filename="", log_pattern="",
        )
        assert profile is not None
        assert profile.log.default_pattern == "{work_dir}/logs/{job_id}.out"

    def test_whitespace_stripped(self):
        profile, _ = build_profile_from_fields(
            name="  dei  ", host="  host  ", username="  user  ",
            port="  22  ", key_filename="  /key  ", log_pattern="  pat  ",
        )
        assert profile is not None
        assert profile.name == "dei"
        assert profile.ssh.host == "host"
        assert profile.ssh.username == "user"
        assert profile.ssh.key_filename == "/key"
        assert profile.log.default_pattern == "pat"


class TestDefaultKeyPath:
    def test_falls_back_to_rsa(self, tmp_path, monkeypatch):
        monkeypatch.setattr("slurmhub.tui.widgets.first_run_wizard.Path.home", lambda: tmp_path)
        # No keys exist — fall back to id_rsa
        assert _default_key_path().endswith("id_rsa")

    def test_prefers_ed25519_when_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr("slurmhub.tui.widgets.first_run_wizard.Path.home", lambda: tmp_path)
        (tmp_path / ".ssh").mkdir()
        (tmp_path / ".ssh" / "id_ed25519").write_text("k")
        assert _default_key_path().endswith("id_ed25519")


# ── Pilot tests for the screen behaviour ────────────────────────────────


class _HostApp(App):
    """Minimal app that immediately pushes the wizard so pilot can drive it."""

    def __init__(self) -> None:
        super().__init__()
        self.result: object = "unset"

    def on_mount(self) -> None:
        self.push_screen(FirstRunWizardScreen(), callback=self._store)

    def _store(self, value):
        self.result = value
        self.exit()


class TestFirstRunWizardScreenPilot:

    @pytest.mark.asyncio
    async def test_cancel_dismisses_with_none(self):
        async with _HostApp().run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        assert pilot.app.result is None

    @pytest.mark.asyncio
    async def test_save_with_missing_host_shows_error(self):
        async with _HostApp().run_test() as pilot:
            await pilot.pause()
            # Try to click save without entering a host
            screen = pilot.app.screen
            host_input = screen.query_one("#field-host", Input)
            assert host_input.value == ""  # default placeholder is empty
            screen._on_save()
            await pilot.pause()
            status = screen.query_one("#wizard-status", Static)
            assert "host" in str(status.content).lower()

    @pytest.mark.asyncio
    async def test_save_with_valid_input_returns_profile(self):
        async with _HostApp().run_test() as pilot:
            await pilot.pause()
            screen = pilot.app.screen
            screen.query_one("#field-host", Input).value = "login.cluster"
            screen.query_one("#field-name", Input).value = "test"
            screen._on_save()
            await pilot.pause()
        result = pilot.app.result
        assert isinstance(result, ProfileConfig)
        assert result.ssh.host == "login.cluster"
        assert result.name == "test"

    @pytest.mark.asyncio
    async def test_test_button_with_no_host_shows_error(self):
        async with _HostApp().run_test() as pilot:
            await pilot.pause()
            screen = pilot.app.screen
            screen._on_test()
            await pilot.pause()
            status = screen.query_one("#wizard-status", Static)
            assert "host" in str(status.content).lower()

    @pytest.mark.asyncio
    async def test_test_button_failed_connection(self):
        with patch.object(FirstRunWizardScreen, "_probe", return_value=(False, "boom")):
            async with _HostApp().run_test() as pilot:
                await pilot.pause()
                screen = pilot.app.screen
                screen.query_one("#field-host", Input).value = "fake"
                screen._on_test()
                # Wait for the worker to complete
                await pilot.pause()
                await pilot.pause()
                status = screen.query_one("#wizard-status", Static)
                # "boom" should appear once the worker reports back
                assert "boom" in str(status.content)


# ── ConfirmScreen pilot tests ──────────────────────────────────────────


class _ConfirmHostApp(App):
    def __init__(self) -> None:
        super().__init__()
        self.result: object = "unset"

    def on_mount(self) -> None:
        self.push_screen(ConfirmScreen("Add another?"), callback=self._store)

    def _store(self, value):
        self.result = value
        self.exit()


class TestConfirmScreen:
    @pytest.mark.asyncio
    async def test_y_returns_true(self):
        async with _ConfirmHostApp().run_test() as pilot:
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()
        assert pilot.app.result is True

    @pytest.mark.asyncio
    async def test_n_returns_false(self):
        async with _ConfirmHostApp().run_test() as pilot:
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause()
        assert pilot.app.result is False

    @pytest.mark.asyncio
    async def test_escape_returns_false(self):
        async with _ConfirmHostApp().run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        assert pilot.app.result is False
