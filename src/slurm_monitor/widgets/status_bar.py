"""Status bar widget for Slurm Monitor."""

from rich.text import Text
from textual.widgets import Static

from slurm_monitor.squeue_parser import SlurmJob


class StatusBar(Static):
    """Widget showing job counts by state and active filters."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._jobs: list[SlurmJob] = []
        self._filter_text: str = ""
        self._state_filter: str = "ALL"
        self._sort_mode: str = "id"

    def update_stats(
        self,
        jobs: list[SlurmJob],
        filter_text: str = "",
        state_filter: str = "ALL",
        sort_mode: str = "id",
    ) -> None:
        """Update the status bar with current job stats."""
        self._jobs = jobs
        self._filter_text = filter_text
        self._state_filter = state_filter
        self._sort_mode = sort_mode
        self.refresh()

    def render(self) -> Text:
        """Render the status bar."""
        text = Text()

        if not self._jobs:
            text.append(" No jobs ", style="dim")
        else:
            counts: dict[str, int] = {}
            for job in self._jobs:
                counts[job.state] = counts.get(job.state, 0) + 1

            total = len(self._jobs)
            text.append(f" {total} jobs ", style="bold")

            state_badges = {
                "RUNNING": ("on green", "bold white on green"),
                "PENDING": ("on yellow", "bold black on yellow"),
                "COMPLETED": ("on blue", "bold white on blue"),
                "FAILED": ("on red", "bold white on red"),
            }
            for state, (bg_style, text_style) in state_badges.items():
                if state in counts:
                    text.append(" ")
                    text.append(f" {counts[state]} {state.lower()} ", style=text_style)

        # Sort indicator
        sort_icons = {"id": "#", "time": "\u23f1", "name": "A-Z", "state": "\u25cf"}
        sort_label = sort_icons.get(self._sort_mode, self._sort_mode)
        text.append("  Sort: ", style="dim")
        text.append(sort_label, style="bold")

        if self._state_filter != "ALL":
            text.append("  Filter: ", style="dim")
            text.append(self._state_filter, style="yellow bold")

        if self._filter_text:
            text.append("  Search: ", style="dim")
            text.append(f'"{self._filter_text}"', style="cyan")

        return text
