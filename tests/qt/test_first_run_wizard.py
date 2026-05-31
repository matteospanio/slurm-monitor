"""Tests for the Qt first-run wizard dialog."""

from slurmhub.qt.dialogs.first_run_wizard import FirstRunWizard


def test_wizard_builds_profile_from_fields(qtbot):
    wiz = FirstRunWizard(default_name="prod")
    qtbot.addWidget(wiz)

    wiz.host.setText("login.example.org")
    wiz.username.setText("alice")
    wiz.port.setValue(2222)

    profile = wiz.profile()
    assert profile.name == "prod"
    assert profile.ssh.host == "login.example.org"
    assert profile.ssh.username == "alice"
    assert profile.ssh.port == 2222


def test_save_button_disabled_without_host(qtbot):
    from PySide6.QtWidgets import QDialogButtonBox

    wiz = FirstRunWizard()
    qtbot.addWidget(wiz)
    save = wiz.buttons.button(QDialogButtonBox.StandardButton.Save)
    assert not save.isEnabled()
    wiz.host.setText("h")
    assert save.isEnabled()
