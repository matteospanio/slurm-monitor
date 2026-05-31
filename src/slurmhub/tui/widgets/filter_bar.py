"""Filter bar widget for slurmhub."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Input, Static


class FilterBar(Static):
    """Widget for filtering jobs by name search."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
    ]

    class FilterChanged(Message):
        """Posted when the filter text changes."""

        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    class FilterClosed(Message):
        """Posted when the filter bar is closed."""

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Filter jobs by name...", id="filter-input")

    def on_mount(self) -> None:
        self.display = False

    def action_close(self) -> None:
        """Escape: hide the bar, clear the search, and return focus."""
        self.hide()
        self.post_message(self.FilterClosed())

    def show(self, initial_value: str = "") -> None:
        """Show the filter bar and focus the input.

        Args:
            initial_value: pre-populate the input (used when reopening the
                bar for a tab that already has an active search).
        """
        self.display = True
        inp = self.query_one(Input)
        if inp.value != initial_value:
            inp.value = initial_value
        inp.focus()

    def hide(self) -> None:
        """Hide the filter bar and clear the input."""
        inp = self.query_one(Input)
        inp.value = ""
        self.display = False
        self.post_message(self.FilterChanged(""))

    def set_value(self, value: str) -> None:
        """Replace the input value without showing/hiding the bar.

        Used when switching tabs so the displayed text matches the
        newly-active profile's search filter.
        """
        try:
            inp = self.query_one(Input)
        except Exception:
            return
        if inp.value != value:
            inp.value = value

    def on_input_changed(self, event: Input.Changed) -> None:
        self.post_message(self.FilterChanged(event.value))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.hide()
        self.post_message(self.FilterClosed())
