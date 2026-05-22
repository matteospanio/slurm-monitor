"""Job detail panel widget for Slurm Monitor (bottom bar in main view)."""

from typing import Optional

from rich.text import Text
from textual.widgets import Static

from slurm_monitor.squeue_parser import SlurmJob
from slurm_monitor.widgets._utils import truncate_path


class JobDetail(Static):
    """Widget showing a summary of the currently selected job."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._job: Optional[SlurmJob] = None
        self._has_jobs: bool = False

    def set_job(self, job: Optional[SlurmJob], has_jobs: bool = True) -> None:
        """Update the displayed job.

        Args:
            job: The selected job, or None if nothing is selected.
            has_jobs: Whether the job list has any entries at all. Used to
                distinguish "no jobs to show" from "cursor not on a row".
        """
        self._job = job
        self._has_jobs = has_jobs
        self.refresh()

    def render(self) -> Text:
        text = Text()

        if self._job is None:
            if self._has_jobs:
                text.append("No job selected", style="dim")
            else:
                text.append("No jobs to display", style="dim italic")
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
            text.append(truncate_path(job.work_dir, components=3))

        return text
