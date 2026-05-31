"""Tests for the Settings screen: profile editing + TOML round-trip."""

from pathlib import Path

from slurmhub.config import (
    AppConfig,
    ConfigLoader,
    DatabaseConfig,
    ProfileConfig,
    SSHConfig,
)
from slurmhub.gui.controller import AppController
from slurmhub.gui.views.settings_view import (
    SettingsView,
    _format_specific_projects,
    _parse_specific_projects,
)


def _config() -> AppConfig:
    return AppConfig(
        profiles={
            "alpha": ProfileConfig(name="alpha", ssh=SSHConfig(host="alpha.example")),
            "beta": ProfileConfig(name="beta", ssh=SSHConfig(host="beta.example")),
        },
        database=DatabaseConfig(retention_days=7),
    )


def test_specific_projects_round_trip():
    text = "proj1 = /a/{job_id}.out\nproj2 = /b/{job_id}.log"
    parsed = _parse_specific_projects(text)
    assert parsed == {"proj1": "/a/{job_id}.out", "proj2": "/b/{job_id}.log"}
    assert _parse_specific_projects(_format_specific_projects(parsed)) == parsed


def test_settings_loads_profiles(qtbot):
    controller = AppController(_config(), demo=False)
    view = SettingsView(controller)
    qtbot.addWidget(view)
    assert view.profile_list.count() == 2
    # First profile loaded into the form.
    assert view.f_host.text() == "alpha.example"
    controller.shutdown()


def test_settings_save_writes_toml(qtbot, tmp_path):
    target = tmp_path / "config.toml"
    controller = AppController(_config(), demo=False, config_path=target)
    view = SettingsView(controller)
    qtbot.addWidget(view)

    # Edit the selected profile's host, then save.
    view.f_host.setText("edited.example")
    view._save()

    assert target.exists()
    reloaded = ConfigLoader.load(target)
    hosts = {p.ssh.host for p in reloaded.profiles.values()}
    assert "edited.example" in hosts
    controller.shutdown()


def test_settings_add_and_remove_profile(qtbot):
    controller = AppController(_config(), demo=False)
    view = SettingsView(controller)
    qtbot.addWidget(view)

    view._add_profile()
    assert view.profile_list.count() == 3

    # Select the new one and remove it.
    view.profile_list.setCurrentRow(2)
    view._remove_profile()
    assert view.profile_list.count() == 2
    controller.shutdown()


def test_settings_readonly_in_demo(qtbot):
    controller = AppController(_config(), demo=True)
    view = SettingsView(controller)
    qtbot.addWidget(view)
    assert not view.save_button.isEnabled()
    controller.shutdown()


def test_settings_save_requires_host(qtbot, tmp_path, monkeypatch):
    target = tmp_path / "config.toml"
    controller = AppController(_config(), demo=False, config_path=target)
    view = SettingsView(controller)
    qtbot.addWidget(view)

    captured: dict[str, str] = {}

    def _warning(_parent, title: str, text: str) -> None:
        captured["title"] = title
        captured["text"] = text

    monkeypatch.setattr(
        "slurmhub.gui.views.settings_view.QMessageBox.warning", _warning
    )

    view.f_host.setText("")
    view._save()

    assert not target.exists()
    assert captured["title"] == "Invalid profile settings"
    assert "missing the SSH host" in captured["text"]
    assert view.status.text() == "Fix profile validation errors before saving."
    controller.shutdown()


def test_settings_save_rejects_missing_ssh_key_file(qtbot, tmp_path, monkeypatch):
    target = tmp_path / "config.toml"
    controller = AppController(_config(), demo=False, config_path=target)
    view = SettingsView(controller)
    qtbot.addWidget(view)

    captured: dict[str, str] = {}

    def _warning(_parent, title: str, text: str) -> None:
        captured["title"] = title
        captured["text"] = text

    monkeypatch.setattr(
        "slurmhub.gui.views.settings_view.QMessageBox.warning", _warning
    )

    missing_key = tmp_path / "id_rsa_missing"
    view.f_key.setText(str(missing_key))
    view._save()

    assert not target.exists()
    assert captured["title"] == "Invalid profile settings"
    assert "does not exist" in captured["text"]
    assert view.status.text() == "Fix profile validation errors before saving."
    controller.shutdown()
