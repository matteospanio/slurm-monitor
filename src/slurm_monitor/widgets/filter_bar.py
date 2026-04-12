"""Filter bar widget for Slurm Monitor."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Input, Static


class FilterBar(Static):
    """Widget for filtering jobs by name search."""

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

    def show(self) -> None:
        """Show the filter bar and focus the input."""
        self.display = True
        self.query_one(Input).focus()

    def hide(self) -> None:
        """Hide the filter bar and clear the input."""
        inp = self.query_one(Input)
        inp.value = ""
        self.display = False
        self.post_message(self.FilterChanged(""))

    def on_input_changed(self, event: Input.Changed) -> None:
        self.post_message(self.FilterChanged(event.value))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.hide()
        self.post_message(self.FilterClosed())
