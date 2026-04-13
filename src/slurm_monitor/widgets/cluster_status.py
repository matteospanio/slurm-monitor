"""Cluster-wide queue status widget for Slurm Monitor."""

from typing import Optional

from rich.text import Text
from textual.widgets import Static

from slurm_monitor.queue_stats import ClusterQueueStats


class ClusterStatus(Static):
    """Widget showing cluster-wide job queue totals."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._stats: Optional[ClusterQueueStats] = None

    def update_stats(self, stats: Optional[ClusterQueueStats]) -> None:
        """Update the displayed cluster stats."""
        self._stats = stats
        self.refresh()

    def render(self) -> Text:
        text = Text()
        text.append(" Cluster: ", style="bold")

        if self._stats is None:
            text.append("waiting for data\u2026", style="dim")
            return text

        text.append(str(self._stats.total_running), style="green bold")
        text.append(" running", style="dim")
        text.append(" | ", style="dim")
        text.append(str(self._stats.total_pending), style="yellow bold")
        text.append(" pending", style="dim")
        if self._stats.total_other > 0:
            text.append(" | ", style="dim")
            text.append(str(self._stats.total_other), style="dim bold")
            text.append(" other", style="dim")

        return text
