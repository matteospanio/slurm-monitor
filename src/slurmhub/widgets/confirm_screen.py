"""Generic yes/no confirmation modal.

Pushed when an action would change cluster state (e.g. ``scancel``).
Dismisses with ``True`` on Enter / ``y``, ``False`` on Escape / ``n``.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmScreen(ModalScreen[bool]):
    """Modal dialog asking the user to confirm a (potentially destructive) action."""

    BINDINGS = [
        Binding("escape", "deny", "Cancel", priority=True),
        Binding("n", "deny", "No"),
        Binding("y", "confirm", "Yes"),
        Binding("enter", "confirm", "Yes", show=False),
    ]

    CSS = """
    ConfirmScreen {
        align: center middle;
    }

    #confirm-dialog {
        width: 60;
        max-width: 90%;
        height: auto;
        background: $surface;
        border: round $warning;
        padding: 1 2;
    }

    #confirm-dialog.-danger {
        border: round $error;
    }

    #confirm-message {
        height: auto;
        margin-bottom: 1;
    }

    #confirm-buttons {
        height: 3;
        align-horizontal: right;
    }

    #confirm-buttons Button {
        margin: 0 1;
    }

    #confirm-hint {
        height: 1;
        color: $text-muted;
        text-align: center;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        message: str,
        *,
        dangerous: bool = False,
        confirm_label: str = "Yes",
        cancel_label: str = "Cancel",
    ) -> None:
        super().__init__()
        self.message = message
        self.dangerous = dangerous
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label

    def compose(self) -> ComposeResult:
        classes = "-danger" if self.dangerous else ""
        with Container(id="confirm-dialog", classes=classes):
            yield Static(self.message, id="confirm-message")
            with Horizontal(id="confirm-buttons"):
                variant = "error" if self.dangerous else "primary"
                yield Button(self.cancel_label, id="cancel-btn")
                yield Button(self.confirm_label, id="confirm-btn", variant=variant)
            yield Static("y to confirm · n / Esc to cancel", id="confirm-hint")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-btn":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_deny(self) -> None:
        self.dismiss(False)
