"""Tests for PasswordPromptScreen widget."""

from slurmhub.tui.widgets.password_prompt import PasswordPromptScreen


class TestPasswordPromptScreen:
    """Test suite for PasswordPromptScreen."""

    def test_stores_host_and_username(self):
        screen = PasswordPromptScreen(host="cluster.edu", username="alice")
        assert screen.host == "cluster.edu"
        assert screen.username == "alice"

    def test_stores_host_without_username(self):
        screen = PasswordPromptScreen(host="cluster.edu")
        assert screen.host == "cluster.edu"
        assert screen.username == ""

    def test_is_modal_screen(self):
        from textual.screen import ModalScreen

        screen = PasswordPromptScreen(host="cluster.edu", username="alice")
        assert isinstance(screen, ModalScreen)

    def test_has_escape_binding(self):
        bindings = {b[0] for b in PasswordPromptScreen.BINDINGS}
        assert "escape" in bindings
