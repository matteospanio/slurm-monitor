"""Modal text-input for editing a favourite's note."""

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class NoteInputScreen(ModalScreen[Optional[str]]):
    """Prompt for a favourite's note.

    Dismisses with the entered string on submit (an empty string clears the
    note), or ``None`` on Escape (leave the note unchanged).
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    NoteInputScreen {
        align: center middle;
        background: $background 60%;
    }

    NoteInputScreen #note-dialog {
        width: 70%;
        min-width: 50;
        max-width: 90;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 2 4;
    }

    NoteInputScreen #note-label {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }

    NoteInputScreen #note-hint {
        width: 100%;
        color: $text-muted;
        margin-bottom: 1;
    }

    NoteInputScreen #note-input {
        width: 100%;
    }
    """

    def __init__(self, job_id: str, initial: str = "") -> None:
        super().__init__()
        self.job_id = job_id
        self.initial = initial

    def compose(self) -> ComposeResult:
        with Vertical(id="note-dialog"):
            yield Static(
                f"Note for job [bold]{self.job_id}[/bold]", id="note-label"
            )
            yield Static(
                "Enter a label or note. Submit to save (empty clears it); "
                "Escape to cancel.",
                id="note-hint",
            )
            yield Input(
                value=self.initial,
                placeholder="e.g. best hyperparams, baseline run",
                id="note-input",
            )

    def on_mount(self) -> None:
        self.query_one("#note-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)
