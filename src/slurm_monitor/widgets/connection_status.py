"""Connection status widget for Slurm Monitor."""

from typing import Optional

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


class ConnectionStatus(Static):
    """Widget displaying connection status and information."""

    host: reactive[str] = reactive("localhost")
    last_updated: reactive[Optional[str]] = reactive(None)
    is_loading: reactive[bool] = reactive(False)
    error_message: reactive[Optional[str]] = reactive(None)

    def render(self) -> Text:
        """Render the connection status."""
        text = Text()

        text.append("Host: ", style="dim")
        text.append(self.host, style="bold cyan")
        text.append(" | ")

        if self.is_loading:
            text.append("Updating...", style="yellow")
        elif self.error_message:
            text.append(f"Error: {self.error_message}", style="red")
        elif self.last_updated:
            text.append("Updated: ", style="dim")
            text.append(self.last_updated, style="green")
        else:
            text.append("Not connected", style="dim")

        return text
