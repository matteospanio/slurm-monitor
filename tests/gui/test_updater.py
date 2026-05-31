"""Tests for the in-app update check (version comparison + flow)."""

from slurmhub.gui import updater
from slurmhub.gui.updater import UpdateInfo, check_for_update, is_newer


def test_is_newer():
    assert is_newer("1.3.0", "1.2.0")
    assert is_newer("v2.0.0", "1.9.9")
    assert is_newer("1.2.1", "1.2.0")
    assert not is_newer("1.2.0", "1.2.0")
    assert not is_newer("1.1.0", "1.2.0")
    # Pre-release trailers are truncated, not crashed on.
    assert not is_newer("1.2.0rc1", "1.2.0")


def test_check_for_update_returns_info_when_newer(monkeypatch):
    monkeypatch.setattr(
        updater, "fetch_latest_release", lambda *a, **k: ("v9.9.9", "https://x/rel")
    )
    info = check_for_update("1.2.0")
    assert isinstance(info, UpdateInfo)
    assert info.version == "v9.9.9"
    assert info.url == "https://x/rel"


def test_check_for_update_none_when_current(monkeypatch):
    monkeypatch.setattr(
        updater, "fetch_latest_release", lambda *a, **k: ("1.2.0", "https://x")
    )
    assert check_for_update("1.2.0") is None


def test_check_for_update_none_when_offline(monkeypatch):
    monkeypatch.setattr(updater, "fetch_latest_release", lambda *a, **k: None)
    assert check_for_update("1.2.0") is None
