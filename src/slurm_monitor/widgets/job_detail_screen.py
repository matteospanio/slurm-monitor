"""Full-screen job detail view with scontrol stats and log access."""

from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Static

from slurm_monitor.scontrol_parser import JobDetails, fetch_job_details
from slurm_monitor.squeue_parser import SlurmJob
from slurm_monitor.ssh_wrapper import SSHClient
from slurm_monitor.widgets.log_viewer import LogScreen

# Bar characters for percentage rendering
_BAR_FILLED = "\u2588"
_BAR_EMPTY = "\u2591"
_BAR_WIDTH = 20


def _render_bar(percentage: float) -> Text:
    """Render a colored percentage bar."""
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


class DetailHeader(Static):
    """Header bar for the detail screen."""


class DetailBody(Static):
    """Body content showing job details."""


class JobDetailScreen(Screen):
    """Full-screen job detail view with resource stats and log access."""

    BINDINGS = [
        Binding("escape", "close", "Back", priority=True),
        Binding("q", "close", "Back"),
        Binding("o", "view_stdout", "View stdout"),
        Binding("e", "view_stderr", "View stderr"),
    ]

    CSS = """
    DetailHeader {
        dock: top;
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 1;
    }

    DetailBody {
        padding: 1 2;
    }
    """

    def __init__(
        self,
        job: SlurmJob,
        ssh_client: SSHClient,
        ssh_timeout: int = 10,
    ):
        super().__init__()
        self.job = job
        self.ssh_client = ssh_client
        self.ssh_timeout = ssh_timeout
        self.details: Optional[JobDetails] = None

    def compose(self) -> ComposeResult:
        yield DetailHeader(f" Job {self.job.job_id}: {self.job.name}")
        yield DetailBody(id="detail-body")
        yield Footer()

    def on_mount(self) -> None:
        self._render_loading()
        self.run_worker(self._fetch, thread=True, exclusive=True)

    def _render_loading(self) -> None:
        body = self.query_one("#detail-body", DetailBody)
        text = Text()
        text.append("Loading job details...", style="dim italic")
        body.update(text)

    def _fetch(self) -> Optional[JobDetails]:
        return fetch_job_details(self.ssh_client, self.job.job_id, self.ssh_timeout)

    def on_worker_state_changed(self, event) -> None:
        from textual.worker import WorkerState

        if event.state == WorkerState.SUCCESS:
            self.details = event.worker.result
            self._render_details()
        elif event.state == WorkerState.ERROR:
            body = self.query_one("#detail-body", DetailBody)
            body.update(Text("Failed to fetch job details", style="red"))

    def _render_details(self) -> None:
        body = self.query_one("#detail-body", DetailBody)
        text = Text()
        job = self.job
        d = self.details

        # Header info
        text.append("Job ID:    ", style="dim")
        text.append(job.job_id, style="bold")
        text.append("\nName:      ", style="dim")
        text.append(job.name, style="bold")
        text.append("\nState:     ", style="dim")

        state_colors = {
            "RUNNING": "green",
            "PENDING": "yellow",
            "COMPLETED": "blue",
            "FAILED": "red",
            "CANCELLED": "magenta",
        }
        state_color = state_colors.get(job.state, "white")
        text.append(job.state, style=f"bold {state_color}")

        if d:
            # Time
            text.append("\n\n")
            text.append("Time", style="bold underline")
            text.append("\n  Elapsed:   ", style="dim")
            text.append(d.run_time)
            text.append("\n  Limit:     ", style="dim")
            text.append(d.time_limit)
            text.append("\n  Progress:  ", style="dim")
            text.append_text(_render_bar(d.time_percentage))

            # Memory
            if d.mem_requested:
                text.append("\n\n")
                text.append("Memory", style="bold underline")
                text.append("\n  Requested: ", style="dim")
                text.append(d.mem_requested)
                if d.mem_used:
                    text.append("\n  Used:      ", style="dim")
                    text.append(d.mem_used)
                    text.append("\n  Usage:     ", style="dim")
                    text.append_text(_render_bar(d.mem_percentage))

            # Resources
            text.append("\n\n")
            text.append("Resources", style="bold underline")
            if d.num_cpus:
                text.append("\n  CPUs:      ", style="dim")
                text.append(str(d.num_cpus))
            if d.partition:
                text.append("\n  Partition: ", style="dim")
                text.append(d.partition)
            if d.node_list:
                text.append("\n  Nodes:     ", style="dim")
                text.append(d.node_list)

            # Timing
            text.append("\n\n")
            text.append("Schedule", style="bold underline")
            if d.submit_time:
                text.append("\n  Submitted: ", style="dim")
                text.append(d.submit_time)
            if d.start_time:
                text.append("\n  Started:   ", style="dim")
                text.append(d.start_time)
            if d.end_time:
                text.append("\n  End:       ", style="dim")
                text.append(d.end_time)

            # Paths
            if d.command:
                text.append("\n\n")
                text.append("Command", style="bold underline")
                text.append("\n  ", style="dim")
                text.append(d.command)

            text.append("\n\n")
            text.append("Log Files", style="bold underline")
            if d.stdout_path:
                text.append("\n  StdOut:    ", style="dim")
                text.append(d.stdout_path)
            if d.stderr_path:
                text.append("\n  StdErr:    ", style="dim")
                text.append(d.stderr_path)
        else:
            text.append("\n\nNo scontrol data available", style="dim italic")

        text.append("\n\n")
        text.append("Press ", style="dim")
        text.append("o", style="bold")
        text.append(" for stdout, ", style="dim")
        text.append("e", style="bold")
        text.append(" for stderr, ", style="dim")
        text.append("Esc", style="bold")
        text.append(" to go back", style="dim")

        body.update(text)

    def _get_log_path(self, stream: str) -> Optional[str]:
        if not self.details:
            return None
        if stream == "stderr":
            return self.details.stderr_path or None
        return self.details.stdout_path or None

    def action_view_stdout(self) -> None:
        path = self._get_log_path("stdout")
        if path:
            self.app.push_screen(LogScreen(self.job, path, self.ssh_client))
        else:
            self.notify("No stdout path available", severity="warning", timeout=3)

    def action_view_stderr(self) -> None:
        path = self._get_log_path("stderr")
        if path:
            self.app.push_screen(LogScreen(self.job, path, self.ssh_client))
        else:
            self.notify("No stderr path available", severity="warning", timeout=3)

    def action_close(self) -> None:
        self.app.pop_screen()
