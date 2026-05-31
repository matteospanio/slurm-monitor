"""Modal cheatsheet showing the keybindings available in each context."""

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Static

# (key, description) tuples grouped by section. Kept in one place so we
# don't need to inspect runtime BINDINGS — those are oriented around
# rendering the Footer, not building a readable cheatsheet.
_HELP: dict[str, dict[str, list[tuple[str, str]]]] = {
    "main": {
        "Navigation": [
            ("j / k", "Move cursor down / up"),
            ("g / G", "Jump to first / last row"),
            ("h / l", "Switch to previous / next profile tab"),
            ("Enter", "Open the job detail screen"),
            ("d", "Open the cluster dashboard"),
            ("H", "Open the job history & analytics"),
            ("D", "Toggle the bottom detail panel"),
            ("?", "Show this help"),
        ],
        "Filtering & sorting": [
            ("/", "Open the search bar (Esc to cancel)"),
            ("1 / 2 / 3 / 4", "Filter RUNNING / PENDING / COMPLETED / FAILED"),
            ("0", "Clear state filter (show all)"),
            ("s", "Cycle sort: id → time → name → state"),
        ],
        "Job actions": [
            ("y", "Copy the selected job ID to clipboard (OSC 52)"),
            ("c", "Cancel the selected job (confirms first)"),
        ],
        "Session": [
            ("r", "Refresh the active profile now"),
            ("q", "Quit the application"),
        ],
    },
    "detail": {
        "Navigation": [
            ("j / k", "Scroll down / up"),
            ("g / G", "Top / bottom of the detail view"),
            ("Esc / q", "Back to the job list"),
        ],
        "Actions": [
            ("o", "Open the stdout log viewer"),
            ("e", "Open the stderr log viewer"),
            ("v", "Show the submitted batch script"),
            ("c", "Cancel this job (confirms first)"),
            ("f", "Toggle this run as a favourite"),
            ("n", "Edit the favourite's note"),
            ("y", "Copy job ID / paths to clipboard (cycles)"),
            ("?", "Show this help"),
        ],
    },
    "history": {
        "Navigation": [
            ("j / k", "Move cursor down / up"),
            ("g / G", "Jump to first / last row"),
            ("Enter", "Open the selected run's detail screen"),
            ("Esc / q", "Back to the job list"),
        ],
        "View & filter": [
            ("a", "Toggle the usage-aggregates view"),
            ("p", "Toggle current-profile / all-profiles scope"),
            ("t", "Cycle the date range (all / 24h / 7d / 30d)"),
            ("F", "Show favourites only"),
            ("1 / 2 / 3 / 4", "Filter RUNNING / PENDING / COMPLETED / FAILED"),
            ("0", "Clear the state filter"),
            ("/", "Search by job name or ID"),
        ],
        "Favourites": [
            ("f", "Toggle the selected run as a favourite"),
            ("n", "Edit the selected run's note"),
            ("r", "Re-run the query"),
        ],
    },
    "dashboard": {
        "Navigation": [
            ("j / k", "Scroll down / up"),
            ("g / G", "Top / bottom of the dashboard"),
            ("Esc / q", "Back to the job list"),
        ],
        "Actions": [
            ("r", "Refresh sinfo now"),
            ("?", "Show this help"),
        ],
    },
    "log": {
        "Navigation": [
            ("j / k", "Scroll down / up"),
            ("g / G", "Top / bottom of the log"),
            ("Esc / q", "Back"),
        ],
        "Actions": [
            ("f", "Toggle follow / pause auto-scroll"),
            ("/", "Search the log buffer (n/N: next/prev match)"),
            ("w", "Save the log buffer to a local file"),
            ("y", "Copy the highlighted line to clipboard"),
            ("?", "Show this help"),
        ],
    },
}


class HelpScreen(ModalScreen[None]):
    """Modal cheatsheet for the bindings available in a given context."""

    BINDINGS = [
        Binding("escape", "close", "Close", priority=True),
        Binding("q", "close", "Close"),
        Binding("question_mark", "close", "Close"),
    ]

    CSS = """
    HelpScreen {
        align: center middle;
    }

    #help-dialog {
        width: 70;
        max-width: 90%;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: round $accent;
        padding: 1 2;
    }

    #help-title {
        height: 1;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #help-body {
        height: auto;
    }

    #help-hint {
        height: 1;
        margin-top: 1;
        color: $text-muted;
        text-align: center;
    }
    """

    _TITLES = {
        "main": "Job list — keybindings",
        "detail": "Job detail — keybindings",
        "history": "Job history — keybindings",
        "dashboard": "Cluster dashboard — keybindings",
        "log": "Log viewer — keybindings",
    }

    def __init__(self, context: str = "main") -> None:
        super().__init__()
        self.context = context if context in _HELP else "main"

    def compose(self) -> ComposeResult:
        with Container(id="help-dialog"):
            yield Static(self._TITLES[self.context], id="help-title")
            with ScrollableContainer(id="help-body"):
                yield Static(self._render_body())
            yield Static("Esc / q to close", id="help-hint")

    def _render_body(self) -> Text:
        text = Text()
        groups = _HELP[self.context]
        first = True
        for section, entries in groups.items():
            if not first:
                text.append("\n")
            first = False
            text.append(section, style="bold underline")
            text.append("\n")
            for key, desc in entries:
                text.append(f"  {key:<18}", style="cyan bold")
                text.append(desc, style="default")
                text.append("\n")
        return text

    def action_close(self) -> None:
        self.dismiss(None)
