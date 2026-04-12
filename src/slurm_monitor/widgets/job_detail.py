"""Job detail panel widget for Slurm Monitor."""

from typing import Optional

from rich.text import Text
from textual.widgets import Static

from slurm_monitor.squeue_parser import SlurmJob


class JobDetail(Static):
    """Widget showing details of the currently selected job."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._job: Optional[SlurmJob] = None
        self._log_path: Optional[str] = None

    def set_job(self, job: Optional[SlurmJob], log_path: Optional[str] = None) -> None:
        """Update the displayed job details."""
        self._job = job
        self._log_path = log_path
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
        text.append("  Time: ", style="dim")
        text.append(job.time, style="bold")

        if job.work_dir:
            text.append("\nWork Dir: ", style="dim")
            text.append(job.work_dir)

        if self._log_path:
            text.append("\nLog Path: ", style="dim")
            text.append(self._log_path, style="italic")

        return text
