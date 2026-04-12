"""Connection status widget for Slurm Monitor."""

from typing import Optional

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


class ConnectionStatus(Static):
    """Widget displaying connection status and information."""

    host: reactive[str] = reactive("localhost")
    profile_name: reactive[str] = reactive("")
    last_updated: reactive[Optional[str]] = reactive(None)
    is_loading: reactive[bool] = reactive(False)
    error_message: reactive[Optional[str]] = reactive(None)

    def render(self) -> Text:
        """Render the connection status."""
        text = Text()

        # Colored dot indicator
        if self.is_loading:
            text.append("\u25cf ", style="yellow")
        elif self.error_message:
            text.append("\u25cf ", style="red")
        elif self.last_updated:
            text.append("\u25cf ", style="green")
        else:
            text.append("\u25cb ", style="dim")

        # Profile name and host
        if self.profile_name:
            text.append(self.profile_name, style="bold")
            text.append(f" ({self.host})", style="dim")
        else:
            text.append(self.host, style="bold")

        text.append(" \u2502 ", style="dim")

        if self.is_loading:
            text.append("Updating\u2026", style="yellow")
        elif self.error_message:
            text.append(self.error_message, style="red")
        elif self.last_updated:
            text.append("Updated: ", style="dim")
            text.append(self.last_updated, style="green")
        else:
            text.append("Not connected", style="dim")

        return text
