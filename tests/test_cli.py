"""Tests for the CLI entry point: config-locate + wizard wiring."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from slurm_monitor import cli
from slurm_monitor.config import (
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
        is passed to SlurmMonitorApp.run()."""
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
        with patch("slurm_monitor.app.SlurmMonitorApp", return_value=app_mock) as ctor:
            runner = CliRunner()
            result = runner.invoke(cli.main, [])
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
        with patch("slurm_monitor.app.SlurmMonitorApp") as ctor:
            runner = CliRunner()
            result = runner.invoke(cli.main, [])
            assert result.exit_code != 0
            ctor.assert_not_called()
            assert "Setup cancelled" in result.output or "Setup cancelled" in result.stderr_bytes.decode("utf-8", errors="replace")

    def test_existing_config_skips_wizard(self, monkeypatch, tmp_path):
        target = tmp_path / "config.toml"
        target.write_text("[defaults]\n[profiles.test]\nhost = \"realhost\"\n")
        monkeypatch.setattr(
            ConfigLoader, "locate", staticmethod(lambda p: (target, True))
        )
        wizard_mock = MagicMock()
        monkeypatch.setattr(cli, "run_first_run_wizard", wizard_mock)
        app_mock = MagicMock()
        with patch("slurm_monitor.app.SlurmMonitorApp", return_value=app_mock):
            runner = CliRunner()
            result = runner.invoke(cli.main, [])
            assert result.exit_code == 0, result.output
            wizard_mock.assert_not_called()
            app_mock.run.assert_called_once()

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
        with patch("slurm_monitor.app.SlurmMonitorApp", return_value=app_mock) as ctor:
            runner = CliRunner()
            result = runner.invoke(cli.main, ["--host", "manualhost"])
            assert result.exit_code == 0, result.output
            wizard_mock.assert_not_called()
            (passed_config,), _ = ctor.call_args
            assert passed_config.profiles["default"].ssh.host == "manualhost"
