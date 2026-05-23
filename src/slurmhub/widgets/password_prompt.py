"""Modal password prompt for SSH authentication."""

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class PasswordPromptScreen(ModalScreen[Optional[str]]):
    """Modal screen that prompts the user for an SSH password or key passphrase."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    PasswordPromptScreen {
        align: center middle;
        background: $background 60%;
    }

    PasswordPromptScreen #password-dialog {
        width: 70%;
        min-width: 50;
        max-width: 90;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 2 4;
    }

    PasswordPromptScreen #password-label {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }

    PasswordPromptScreen #password-hint {
        width: 100%;
        color: $text-muted;
        margin-bottom: 1;
    }

    PasswordPromptScreen #password-input {
        width: 100%;
    }
    """

    def __init__(self, host: str, username: str = "") -> None:
        super().__init__()
        self.host = host
        self.username = username

    def compose(self) -> ComposeResult:
        target = f"{self.username}@{self.host}" if self.username else self.host
        with Vertical(id="password-dialog"):
            yield Static(
                f"SSH authentication required for [bold]{target}[/bold]",
                id="password-label",
            )
            yield Static(
                "Enter your password or key passphrase. Press Escape to cancel.",
                id="password-hint",
            )
            yield Input(
                placeholder="Password",
                password=True,
                id="password-input",
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.value:
            self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)
