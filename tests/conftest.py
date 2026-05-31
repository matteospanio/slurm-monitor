"""Global test guards: keep the whole suite non-interactive and offline.

Two safeguards, applied to every test:

1. Force the Qt ``offscreen`` platform for the *entire* suite (not just the GUI
   tests), set before pytest-qt ever builds a ``QApplication``. ``setdefault``
   is deliberately avoided — if the developer's shell already exports
   ``QT_QPA_PLATFORM`` (common under a desktop session / IDE test runner), a
   ``setdefault`` would be a no-op and GUI tests would pop real windows.

2. Fail loudly if any test attempts a real network SSH connection or an
   interactive credential prompt (terminal *or* Qt dialog). "Tests should be
   automatic, not interactive" is then enforced, not merely assumed.
"""

import getpass
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from slurmhub.slurm.ssh import SSHConnectionError


def _forbid(what: str):
    def _raise(*args, **kwargs):
        raise RuntimeError(
            f"Test attempted {what}; tests must stay non-interactive and offline."
        )

    return _raise


def _offline_connect(*args, **kwargs):
    # Real paramiko connects are turned into the app's own "host unreachable"
    # error so on-mount refresh workers degrade gracefully (empty jobs) on every
    # machine — instead of, on a developer box, reaching a live host/agent and
    # popping a password dialog. Tests that assert on connect() itself mock
    # paramiko.SSHClient wholesale, so they never reach this shim.
    raise SSHConnectionError("SSH disabled in tests (offline test environment)")


@pytest.fixture(autouse=True)
def _no_real_ssh_or_interactive_prompts(monkeypatch):
    # No real network SSH — simulate an unreachable host, deterministically.
    monkeypatch.setattr(
        "paramiko.SSHClient.connect", _offline_connect, raising=False
    )
    # No interactive terminal password/passphrase prompt.
    monkeypatch.setattr(getpass, "getpass", _forbid("an interactive getpass() prompt"))
    # No Qt credential/input dialogs (the SSH-password dialog and note editors).
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(
        QInputDialog,
        "getText",
        staticmethod(_forbid("a QInputDialog.getText() prompt")),
        raising=False,
    )
    monkeypatch.setattr(
        QInputDialog,
        "getMultiLineText",
        staticmethod(_forbid("a QInputDialog.getMultiLineText() prompt")),
        raising=False,
    )
