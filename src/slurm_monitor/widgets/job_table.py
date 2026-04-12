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

    def on_mount(self) -> None:
        """Initialize the table when mounted."""
        self.cursor_type = "row"
        self.zebra_stripes = True

        self.add_column("Job ID", key="job_id")
        self.add_column("Name", key="name")
        self.add_column("State", key="state")
        self.add_column("Time", key="time")
        self.add_column("GPUs", key="gpus")
        self.add_column("Work Dir", key="work_dir")

    def update_jobs(self, jobs: list[SlurmJob]) -> None:
        """Update table with new job data."""
        self.clear()

        for job in jobs:
            state_style = self.STATE_COLORS.get(job.state, "white")
            styled_state = Text(job.state, style=f"bold {state_style}")
            gpu_text = job.gpu_display
            styled_gpu = Text(gpu_text, style="cyan") if gpu_text else Text("")

            self.add_row(
                job.job_id,
                job.name,
                styled_state,
                Text(job.time, justify="right"),
                styled_gpu,
                _truncate_path(job.work_dir or ""),
                key=job.job_id,
            )
