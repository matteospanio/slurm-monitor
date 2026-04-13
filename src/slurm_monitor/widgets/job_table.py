"""Job table widget for Slurm Monitor."""

from pathlib import PurePosixPath

from rich.text import Text
from textual.widgets import DataTable

from slurm_monitor.squeue_parser import SlurmJob


def _truncate_path(path: str, components: int = 2) -> str:
    """Truncate a path to the last N components.

    Example: '/home/user/projects/ml/train' -> '../ml/train'
    """
    if not path:
        return ""
    parts = PurePosixPath(path).parts
    if len(parts) <= components:
        return path
    return "../" + "/".join(parts[-components:])


class JobTable(DataTable):
    """DataTable widget for displaying Slurm jobs."""

    STATE_COLORS = {
        "RUNNING": "green",
        "PENDING": "yellow",
        "COMPLETED": "blue",
        "FAILED": "red",
        "CANCELLED": "magenta",
        "TIMEOUT": "red",
        "OUT_OF_MEMORY": "red",
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_job_ids: list[str] = []

    def on_mount(self) -> None:
        """Initialize the table when mounted."""
        self.cursor_type = "row"
        self.zebra_stripes = True

        self.add_column("Job ID", key="job_id")
        self.add_column("Name", key="name")
        self.add_column("State", key="state")
        self.add_column("Time", key="time")
        self.add_column("Reason", key="reason")
        self.add_column("Rank", key="rank")
        self.add_column("Work Dir", key="work_dir")

    def update_jobs(self, jobs: list[SlurmJob]) -> None:
        """Update table with new job data, preserving cursor position."""
        # Save cursor state before clearing
        selected_job_id: str | None = None
        old_cursor_row = self.cursor_row
        if self._current_job_ids and 0 <= old_cursor_row < len(self._current_job_ids):
            selected_job_id = self._current_job_ids[old_cursor_row]

        self.clear()

        for job in jobs:
            state_style = self.STATE_COLORS.get(job.state, "white")
            styled_state = Text(job.state, style=f"bold {state_style}")

            reason_text = Text("")
            rank_text = Text("")
            if job.state == "PENDING":
                if job.pending_reason:
                    reason = job.pending_reason[:20]
                    reason_text = Text(reason, style="yellow")
                if job.queue_rank is not None:
                    rank_text = Text(f"#{job.queue_rank}", style="cyan bold")

            self.add_row(
                job.job_id,
                job.name,
                styled_state,
                Text(job.time, justify="right"),
                reason_text,
                rank_text,
                _truncate_path(job.work_dir or ""),
                key=job.job_id,
            )

        # Update job ID tracking
        self._current_job_ids = [job.job_id for job in jobs]

        # Restore cursor to the same job, or clamp if it disappeared
        if selected_job_id is not None and jobs:
            new_index = next(
                (i for i, j in enumerate(jobs) if j.job_id == selected_job_id),
                None,
            )
            if new_index is not None:
                self.move_cursor(row=new_index, animate=False)
            else:
                self.move_cursor(
                    row=min(old_cursor_row, len(jobs) - 1), animate=False
                )
