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

    def update_stats(
        self,
        jobs: list[SlurmJob],
        filter_text: str = "",
        state_filter: str = "ALL",
    ) -> None:
        """Update the status bar with current job stats."""
        self._jobs = jobs
        self._filter_text = filter_text
        self._state_filter = state_filter
        self.refresh()

    def render(self) -> Text:
        """Render the status bar."""
        text = Text()

        if not self._jobs:
            text.append("No jobs", style="dim")
        else:
            counts: dict[str, int] = {}
            for job in self._jobs:
                counts[job.state] = counts.get(job.state, 0) + 1

            total = len(self._jobs)
            text.append(f"{total} jobs", style="bold")
            text.append(" | ")

            state_styles = {
                "RUNNING": "green",
                "PENDING": "yellow",
                "COMPLETED": "blue",
                "FAILED": "red",
            }
            parts = []
            for state in ["RUNNING", "PENDING", "COMPLETED", "FAILED"]:
                if state in counts:
                    parts.append((f"{counts[state]} {state.lower()}", state_styles.get(state, "white")))

            for i, (part_text, style) in enumerate(parts):
                if i > 0:
                    text.append(" ")
                text.append(part_text, style=style)

        if self._state_filter != "ALL":
            text.append(f" | Filter: {self._state_filter}", style="yellow")

        if self._filter_text:
            text.append(f' | Search: "{self._filter_text}"', style="cyan")

        return text
