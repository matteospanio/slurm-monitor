"""Job detail panel widget for Slurm Monitor (bottom bar in main view)."""

from typing import Optional

from rich.text import Text
from textual.widgets import Static

from slurm_monitor.squeue_parser import SlurmJob


class JobDetail(Static):
    """Widget showing a summary of the currently selected job."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._job: Optional[SlurmJob] = None

    def set_job(self, job: Optional[SlurmJob]) -> None:
        """Update the displayed job."""
        self._job = job
        self.refresh()

    def render(self) -> Text:
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
        text.append("  Time: ", style="dim")
        text.append(job.time, style="bold")

        if job.state == "PENDING":
            if job.pending_reason:
                text.append("  Reason: ", style="dim")
                text.append(job.pending_reason, style="yellow bold")
            if job.queue_rank is not None:
                text.append("  Rank: ", style="dim")
                text.append(f"#{job.queue_rank}", style="cyan bold")
            if job.qos:
                text.append("  QOS: ", style="dim")
                text.append(job.qos, style="bold")
            if job.priority is not None:
                text.append("  Priority: ", style="dim")
                text.append(str(job.priority), style="bold")
            if job.submit_time:
                text.append("  Submitted: ", style="dim")
                text.append(job.submit_time, style="bold")

        if job.work_dir:
            text.append("\nWork Dir: ", style="dim")
            text.append(job.work_dir)

        return text
