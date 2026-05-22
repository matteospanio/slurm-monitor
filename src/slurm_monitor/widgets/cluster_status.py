"""Cluster-wide queue status widget for Slurm Monitor."""

from typing import Optional

from rich.text import Text
from textual.widgets import Static

from slurm_monitor.queue_stats import ClusterQueueStats
from slurm_monitor.scontrol_parser import format_mem_human
from slurm_monitor.sinfo_parser import ClusterCapacity


def _format_mem_mb(mb: int) -> str:
    """Render a megabyte count as a short human string (e.g. ``1.4T``)."""
    if mb <= 0:
        return "0"
    return format_mem_human(mb * 1024 * 1024)


class ClusterStatus(Static):
    """Widget showing cluster-wide job queue totals + optional capacity."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._stats: Optional[ClusterQueueStats] = None
        self._capacity: Optional[ClusterCapacity] = None

    def update_stats(self, stats: Optional[ClusterQueueStats]) -> None:
        """Update the displayed cluster queue stats."""
        self._stats = stats
        self.refresh()

    def update_capacity(self, capacity: Optional[ClusterCapacity]) -> None:
        """Update the optional capacity strip (CPU/GPU/Mem totals)."""
        self._capacity = capacity
        self.refresh()

    def render(self) -> Text:
        text = Text()
        text.append(" Cluster: ", style="bold")

        if self._stats is None:
            text.append("waiting for data\u2026", style="dim")
        else:
            text.append(str(self._stats.total_running), style="green bold")
            text.append(" running", style="dim")
            text.append(" | ", style="dim")
            text.append(str(self._stats.total_pending), style="yellow bold")
            text.append(" pending", style="dim")
            if self._stats.total_other > 0:
                text.append(" | ", style="dim")
                text.append(str(self._stats.total_other), style="dim bold")
                text.append(" other", style="dim")

        cap = self._capacity
        if cap is not None and cap.cpus_total > 0:
            text.append("  \u00b7  ", style="dim")
            text.append(
                f"{cap.cpus_used}/{cap.cpus_total} CPU", style="cyan"
            )
            if cap.gpus_total > 0:
                text.append(" \u00b7 ", style="dim")
                text.append(
                    f"{cap.gpus_used}/{cap.gpus_total} GPU", style="cyan"
                )
            if cap.mem_total_mb > 0:
                text.append(" \u00b7 ", style="dim")
                used_h = _format_mem_mb(cap.mem_used_mb)
                total_h = _format_mem_mb(cap.mem_total_mb)
                text.append(f"{used_h}/{total_h} mem", style="cyan")
            text.append(" \u00b7 ", style="dim")
            text.append(f"{cap.nodes_up} up", style="green")
            if cap.nodes_drain > 0:
                text.append(", ", style="dim")
                text.append(f"{cap.nodes_drain} drain", style="magenta")
            if cap.nodes_down > 0:
                text.append(", ", style="dim")
                text.append(f"{cap.nodes_down} down", style="red")

        return text
