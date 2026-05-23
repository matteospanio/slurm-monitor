"""Status bar widget for slurmhub."""

from typing import Optional

from rich.text import Text
from textual.widgets import Static

from slurmhub.squeue_parser import SlurmJob


class StatusBar(Static):
    """Widget showing job counts by state and active filters."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._jobs: list[SlurmJob] = []
        self._visible_count: Optional[int] = None
        self._filter_text: str = ""
        self._state_filter: str = "ALL"
        self._sort_mode: str = "id"

    def update_stats(
        self,
        jobs: list[SlurmJob],
        filter_text: str = "",
        state_filter: str = "ALL",
        sort_mode: str = "id",
        visible_count: Optional[int] = None,
    ) -> None:
        """Update the status bar with current job stats.

        Args:
            jobs: All jobs (total, pre-filter).
            visible_count: Number of jobs currently visible after
                filters. When None and any filter is active, the bar
                will not show the "N of M shown" suffix.
        """
        self._jobs = jobs
        self._visible_count = visible_count
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
                "RUNNING": "bold white on green",
                "PENDING": "bold black on yellow",
                "COMPLETED": "bold white on blue",
                "FAILED": "bold white on red",
            }
            for state, text_style in state_badges.items():
                if state in counts:
                    text.append(" ")
                    text.append(f" {counts[state]} {state.lower()} ", style=text_style)

            filter_active = (
                self._state_filter != "ALL" or bool(self._filter_text)
            )
            if filter_active and self._visible_count is not None:
                text.append(
                    f"  {self._visible_count} of {total} shown",
                    style="cyan bold",
                )

        # Sort indicator \u2014 full word, no cryptic glyphs
        text.append("  Sort: ", style="dim")
        text.append(self._sort_mode, style="bold")

        if self._state_filter != "ALL":
            text.append("  Filter: ", style="dim")
            text.append(self._state_filter, style="yellow bold")

        if self._filter_text:
            text.append("  Search: ", style="dim")
            text.append(f'"{self._filter_text}"', style="cyan")
            text.append("  ", style="dim")
            text.append("(esc to clear)", style="dim italic")
        else:
            text.append("   ", style="dim")
            text.append("/ search   ? help", style="dim italic")

        return text
