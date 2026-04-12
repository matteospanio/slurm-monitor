"""Job detail panel widget for Slurm Monitor."""

from typing import Optional

from rich.text import Text
from textual.widgets import Static

from slurm_monitor.scontrol_parser import JobDetails
from slurm_monitor.squeue_parser import SlurmJob

# Bar characters for percentage rendering
_BAR_FILLED = "\u2588"
_BAR_EMPTY = "\u2591"
_BAR_WIDTH = 15


def _render_bar(percentage: float) -> Text:
    """Render a percentage bar like [████████░░░░░░░] 53.2%."""
    pct = max(0.0, min(100.0, percentage))
    filled = round(_BAR_WIDTH * pct / 100)
    empty = _BAR_WIDTH - filled

    if pct >= 90:
        color = "red"
    elif pct >= 70:
        color = "yellow"
    else:
        color = "green"

    bar = Text()
    bar.append(_BAR_FILLED * filled, style=color)
    bar.append(_BAR_EMPTY * empty, style="dim")
    bar.append(f" {pct:.1f}%")
    return bar


class JobDetail(Static):
    """Widget showing details of the currently selected job."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._job: Optional[SlurmJob] = None
        self._log_path: Optional[str] = None
        self._details: Optional[JobDetails] = None

    def set_job(self, job: Optional[SlurmJob], log_path: Optional[str] = None) -> None:
        """Update the displayed job (basic info)."""
        self._job = job
        self._log_path = log_path
        if job is None:
            self._details = None
        self.refresh()

    def set_details(self, details: Optional[JobDetails]) -> None:
        """Update extended scontrol details for the current job."""
        self._details = details
        self.refresh()

    def render(self) -> Text:
        """Render the job detail panel."""
        text = Text()

        if self._job is None:
            text.append("No job selected", style="dim")
            return text

        job = self._job
        text.append("Job ID: ", style="dim")
        text.append(job.job_id, style="bold")
        text.append("  Name: ", style="dim")
        text.append(job.name, style="bold")
        text.append("  State: ", style="dim")
        text.append(job.state, style="bold")

        d = self._details
        if d:
            # Time bar
            text.append("\nTime:   ", style="dim")
            text.append(f"{d.run_time} / {d.time_limit}  ")
            text.append_text(_render_bar(d.time_percentage))

            # Memory bar
            if d.mem_requested:
                text.append("\nMemory: ", style="dim")
                if d.mem_used:
                    text.append(f"{d.mem_used} / {d.mem_requested}  ")
                    text.append_text(_render_bar(d.mem_percentage))
                else:
                    text.append(f"Requested: {d.mem_requested}")

            # Resources line
            parts = []
            if d.num_cpus:
                parts.append(f"CPUs: {d.num_cpus}")
            if d.partition:
                parts.append(f"Partition: {d.partition}")
            if d.node_list:
                parts.append(f"Nodes: {d.node_list}")
            if parts:
                text.append("\n")
                text.append("  ".join(parts), style="dim")

            # Times
            if d.submit_time or d.start_time:
                text.append("\n")
                if d.submit_time:
                    text.append("Submitted: ", style="dim")
                    text.append(d.submit_time)
                    text.append("  ")
                if d.start_time:
                    text.append("Started: ", style="dim")
                    text.append(d.start_time)

            # Paths
            if d.stdout_path:
                text.append("\nStdOut: ", style="dim")
                text.append(d.stdout_path, style="italic")
            if d.stderr_path and d.stderr_path != d.stdout_path:
                text.append("\nStdErr: ", style="dim")
                text.append(d.stderr_path, style="italic")
        else:
            # Fallback to basic info when details not yet loaded
            text.append("  Time: ", style="dim")
            text.append(job.time, style="bold")
            if job.work_dir:
                text.append("\nWork Dir: ", style="dim")
                text.append(job.work_dir)
            if self._log_path:
                text.append("\nLog Path: ", style="dim")
                text.append(self._log_path, style="italic")

        return text
