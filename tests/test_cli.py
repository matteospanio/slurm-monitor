"""Tests for the CLI entry point: config-locate + wizard wiring."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from slurmhub import cli
from slurmhub.config import (
    AppConfig,
    ConfigLoader,
    LogConfig,
    ProfileConfig,
    SSHConfig,
)


class TestConfigLocate:
    def test_locate_returns_explicit_path_when_provided(self, tmp_path):
        p = tmp_path / "myconfig.toml"
        # Doesn't need to exist for the path-honouring branch
        path, found = ConfigLoader.locate(p)
        assert path == p
        assert found is False
        p.write_text("[defaults]\n")
        path, found = ConfigLoader.locate(p)
        assert path == p
        assert found is True

    def test_locate_returns_first_default_when_none_exist(self, monkeypatch, tmp_path):
        # Point the default search paths into a fresh temp directory so
        # nothing under the developer's $HOME accidentally satisfies the
        # check.
        fake_paths = [
            tmp_path / "a.toml",
            tmp_path / "b.toml",
        ]
        monkeypatch.setattr(ConfigLoader, "DEFAULT_CONFIG_PATHS", fake_paths)
        path, found = ConfigLoader.locate(None)
        assert path == fake_paths[0]
        assert found is False

    def test_locate_finds_existing_default(self, monkeypatch, tmp_path):
        fake_paths = [
            tmp_path / "a.toml",
            tmp_path / "b.toml",
        ]
        fake_paths[1].write_text("[defaults]\n")
        monkeypatch.setattr(ConfigLoader, "DEFAULT_CONFIG_PATHS", fake_paths)
        path, found = ConfigLoader.locate(None)
        assert path == fake_paths[1]
        assert found is True


class TestCliWizardWiring:
    def _make_config(self) -> AppConfig:
        return AppConfig(
            profiles={
                "test": ProfileConfig(
                    name="test",
                    ssh=SSHConfig(host="wizardhost"),
                    log=LogConfig(),
                )
            }
        )

    def test_no_config_triggers_wizard_then_runs_app(self, monkeypatch, tmp_path):
        """When no config exists, wizard is invoked and the resulting config
        is passed to SlurmhubApp.run()."""
        # Force `locate` to report "not found"
        target = tmp_path / "config.toml"
        monkeypatch.setattr(
            ConfigLoader, "locate", staticmethod(lambda p: (target, False))
        )
        # Stub the wizard so it returns a canned config without running Textual
        config = self._make_config()
        wizard_mock = MagicMock(return_value=config)
        monkeypatch.setattr(cli, "run_first_run_wizard", wizard_mock)

        app_mock = MagicMock()
        with patch("slurmhub.app.SlurmhubApp", return_value=app_mock) as ctor:
            runner = CliRunner()
            # --tui exercises the (UI-agnostic) wizard + config wiring against
            # the Textual launch path that this test mocks.
            result = runner.invoke(cli.main, ["--tui"])
            assert result.exit_code == 0, result.output
            wizard_mock.assert_called_once_with(target)
            ctor.assert_called_once()
            (passed_config,), _ = ctor.call_args
            assert passed_config is config
            app_mock.run.assert_called_once()

    def test_wizard_cancellation_exits_nonzero(self, monkeypatch, tmp_path):
        target = tmp_path / "config.toml"
        monkeypatch.setattr(
            ConfigLoader, "locate", staticmethod(lambda p: (target, False))
        )
        monkeypatch.setattr(
            cli, "run_first_run_wizard", lambda p: None
        )
        with patch("slurmhub.app.SlurmhubApp") as ctor:
            runner = CliRunner()
            result = runner.invoke(cli.main, ["--tui"])
            assert result.exit_code != 0
            ctor.assert_not_called()
            assert "Setup cancelled" in result.output or "Setup cancelled" in result.stderr_bytes.decode("utf-8", errors="replace")

    def test_gui_first_run_invokes_qt_wizard(self, monkeypatch, tmp_path):
        """GUI first-run uses the Qt wizard, then launches the GUI."""
        target = tmp_path / "config.toml"
        monkeypatch.setattr(
            ConfigLoader, "locate", staticmethod(lambda p: (target, False))
        )
        config = self._make_config()
        wizard = MagicMock(return_value=config)
        monkeypatch.setattr(
            "slurmhub.qt.dialogs.first_run_wizard.run_first_run_wizard_qt", wizard
        )
        gui = MagicMock()
        with patch("slurmhub.qt.app.run_gui", gui), patch("slurmhub.app.SlurmhubApp") as tui:
            runner = CliRunner()
            result = runner.invoke(cli.main, [])
            assert result.exit_code == 0, result.output
            wizard.assert_called_once_with(target)
            gui.assert_called_once()
            tui.assert_not_called()

    def test_existing_config_skips_wizard(self, monkeypatch, tmp_path):
        target = tmp_path / "config.toml"
        target.write_text("[defaults]\n[profiles.test]\nhost = \"realhost\"\n")
        monkeypatch.setattr(
            ConfigLoader, "locate", staticmethod(lambda p: (target, True))
        )
        wizard_mock = MagicMock()
        monkeypatch.setattr(cli, "run_first_run_wizard", wizard_mock)
        app_mock = MagicMock()
        with patch("slurmhub.app.SlurmhubApp", return_value=app_mock):
            runner = CliRunner()
            result = runner.invoke(cli.main, ["--tui"])
            assert result.exit_code == 0, result.output
            wizard_mock.assert_not_called()
            app_mock.run.assert_called_once()

    def test_default_launches_gui_not_tui(self, monkeypatch, tmp_path):
        """With no UI flag, the GUI is launched and the Textual app is not."""
        target = tmp_path / "config.toml"
        target.write_text('[defaults]\n[profiles.test]\nhost = "realhost"\n')
        monkeypatch.setattr(
            ConfigLoader, "locate", staticmethod(lambda p: (target, True))
        )
        gui_mock = MagicMock()
        with patch("slurmhub.qt.app.run_gui", gui_mock) as gui, patch(
            "slurmhub.app.SlurmhubApp"
        ) as tui_ctor:
            runner = CliRunner()
            result = runner.invoke(cli.main, [])
            assert result.exit_code == 0, result.output
            gui.assert_called_once()
            tui_ctor.assert_not_called()

    def test_host_flag_skips_wizard(self, monkeypatch, tmp_path):
        """--host should bypass the wizard entirely, even with no config on disk."""
        monkeypatch.setattr(
            ConfigLoader,
            "locate",
            staticmethod(lambda p: (tmp_path / "config.toml", False)),
        )
        wizard_mock = MagicMock()
        monkeypatch.setattr(cli, "run_first_run_wizard", wizard_mock)
        app_mock = MagicMock()
        with patch("slurmhub.app.SlurmhubApp", return_value=app_mock) as ctor:
            runner = CliRunner()
            result = runner.invoke(cli.main, ["--host", "manualhost", "--tui"])
            assert result.exit_code == 0, result.output
            wizard_mock.assert_not_called()
            (passed_config,), _ = ctor.call_args
            assert passed_config.profiles["default"].ssh.host == "manualhost"
