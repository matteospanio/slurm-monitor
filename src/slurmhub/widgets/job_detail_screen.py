"""Full-screen job detail view with scontrol stats and log access."""

from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widgets import Footer, Static

from slurmhub.scontrol_parser import JobDetails, fetch_job_details
from slurmhub.squeue_parser import SlurmJob
from slurmhub.ssh_wrapper import SSHClient
from slurmhub.widgets._bars import render_bar as _render_bar
from slurmhub.widgets.log_viewer import LogScreen

_SEPARATOR = "\u2500" * 40


class DetailHeader(Static):
    """Header bar for the detail screen."""


class DetailSection(Static):
    """A section within the detail body."""


class JobDetailScreen(Screen):
    """Full-screen job detail view with resource stats and log access."""

    BINDINGS = [
        Binding("escape", "close", "Back", priority=True),
        Binding("q", "close", "Back"),
        Binding("o", "view_stdout", "View stdout"),
        Binding("e", "view_stderr", "View stderr"),
        Binding("v", "view_script", "Batch script"),
        Binding("c", "cancel_job", "scancel"),
        Binding("y", "yank", "Copy"),
        Binding("question_mark", "help", "Help"),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("g", "scroll_home", "Top", show=False),
        Binding("G,shift+g", "scroll_end", "Bottom", show=False),
    ]

    CSS = """
    DetailHeader {
        dock: top;
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 1;
    }

    #detail-scroll {
        height: 1fr;
    }

    DetailSection {
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
        # Cycle index for the `y` (yank) action — increments each time.
        self._yank_idx: int = 0

    def compose(self) -> ComposeResult:
        yield DetailHeader(f" Job {self.job.job_id}: {self.job.name}")
        with ScrollableContainer(id="detail-scroll"):
            yield DetailSection(id="detail-body")
        yield Footer()

    def on_mount(self) -> None:
        self._render_loading()
        self.run_worker(self._fetch, thread=True, exclusive=True)

    def _render_loading(self) -> None:
        body = self.query_one("#detail-body", DetailSection)
        text = Text()
        text.append("Loading job details\u2026", style="dim italic")
        body.update(text)

    def _fetch(self) -> Optional[JobDetails]:
        return fetch_job_details(self.ssh_client, self.job.job_id, self.ssh_timeout)

    def on_worker_state_changed(self, event) -> None:
        from textual.worker import WorkerState

        # Only react to the detail-fetch worker. Other workers
        # (e.g. detail-scancel-*) report their own results via notify.
        worker_name = event.worker.name or ""
        if worker_name.startswith("detail-scancel-"):
            return

        if event.state == WorkerState.SUCCESS:
            self.details = event.worker.result
            self._render_details()
        elif event.state == WorkerState.ERROR:
            body = self.query_one("#detail-body", DetailSection)
            body.update(Text("Failed to fetch job details", style="red"))

    def _render_details(self) -> None:
        body = self.query_one("#detail-body", DetailSection)
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
            # Time section
            text.append(f"\n\n{_SEPARATOR}\n")
            text.append("Time", style="bold underline")
            text.append("\n  Elapsed:   ", style="dim")
            text.append(d.run_time)
            text.append("\n  Limit:     ", style="dim")
            text.append(d.time_limit)
            text.append("\n  Progress:  ", style="dim")
            text.append_text(_render_bar(d.time_percentage))

            # Memory section
            if d.mem_requested:
                text.append(f"\n\n{_SEPARATOR}\n")
                text.append("Memory", style="bold underline")
                text.append("\n  Requested: ", style="dim")
                text.append(d.mem_requested)
                if d.mem_used:
                    text.append("\n  Used:      ", style="dim")
                    text.append(d.mem_used)
                    text.append("\n  Usage:     ", style="dim")
                    text.append_text(_render_bar(d.mem_percentage))

            # GPUs section
            if d.num_gpus > 0:
                text.append(f"\n\n{_SEPARATOR}\n")
                text.append("GPUs", style="bold underline")
                gpu_label = f"{d.num_gpus}x {d.gpu_type}" if d.gpu_type else str(d.num_gpus)
                text.append(f"\n  Allocated: ", style="dim")
                text.append(gpu_label, style="cyan")
                if d.gpus:
                    for gpu in d.gpus:
                        text.append(f"\n  GPU {gpu.index}:    ", style="dim")
                        text.append(f"{gpu.name}  ", style="cyan")
                        text.append("Util: ", style="dim")
                        text.append_text(_render_bar(gpu.utilization))
                        text.append(f"\n             Mem:  ", style="dim")
                        text.append(f"{gpu.mem_used_mb}M / {gpu.mem_total_mb}M  ")
                        text.append_text(_render_bar(gpu.mem_percentage))

            # Resources section
            text.append(f"\n\n{_SEPARATOR}\n")
            text.append("Resources", style="bold underline")
            if d.num_cpus:
                text.append("\n  CPUs:      ", style="dim")
                text.append(str(d.num_cpus))
            if d.num_gpus:
                text.append("\n  GPUs:      ", style="dim")
                gpu_label = f"{d.num_gpus}x {d.gpu_type}" if d.gpu_type else str(d.num_gpus)
                text.append(gpu_label)
            if d.partition:
                text.append("\n  Partition: ", style="dim")
                text.append(d.partition)
            if d.node_list:
                text.append("\n  Nodes:     ", style="dim")
                text.append(d.node_list)

            # Timing section
            text.append(f"\n\n{_SEPARATOR}\n")
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

            # Paths section
            if d.command:
                text.append(f"\n\n{_SEPARATOR}\n")
                text.append("Command", style="bold underline")
                text.append("\n  ", style="dim")
                text.append(d.command)

            text.append(f"\n\n{_SEPARATOR}\n")
            text.append("Log Files", style="bold underline")
            if d.stdout_path:
                text.append("\n  StdOut:    ", style="dim")
                text.append(d.stdout_path)
            if d.stderr_path:
                text.append("\n  StdErr:    ", style="dim")
                text.append(d.stderr_path)
        else:
            text.append("\n\nNo scontrol data available", style="dim italic")

        text.append(f"\n\n{_SEPARATOR}\n")
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
            self.app.push_screen(LogScreen(self.job, path, self.ssh_client, stream="stdout"))
        else:
            self.notify("No stdout path available", severity="warning", timeout=3)

    def action_view_stderr(self) -> None:
        path = self._get_log_path("stderr")
        if path:
            self.app.push_screen(LogScreen(self.job, path, self.ssh_client, stream="stderr"))
        else:
            self.notify("No stderr path available", severity="warning", timeout=3)

    def action_close(self) -> None:
        self.app.pop_screen()

    def action_help(self) -> None:
        from slurmhub.widgets.help_screen import HelpScreen

        self.app.push_screen(HelpScreen(context="detail"))

    def _yank_targets(self) -> list[tuple[str, str]]:
        """Build the list of (label, value) yank targets for this job.

        Order: job_id → stdout path → stderr path → work_dir, skipping
        any target whose value is empty.
        """
        targets: list[tuple[str, str]] = [("job ID", self.job.job_id)]
        d = self.details
        if d:
            if d.stdout_path:
                targets.append(("stdout path", d.stdout_path))
            if d.stderr_path:
                targets.append(("stderr path", d.stderr_path))
        if self.job.work_dir:
            targets.append(("work dir", self.job.work_dir))
        return targets

    def action_view_script(self) -> None:
        """Open the read-only batch-script viewer for this job."""
        from slurmhub.widgets.batch_script_screen import BatchScriptScreen

        self.app.push_screen(
            BatchScriptScreen(self.job, self.ssh_client, self.ssh_timeout)
        )

    def action_cancel_job(self) -> None:
        """Delegate to the app's scancel action so confirmation+SSH live in one place."""
        # The app owns the SSH client and the per-profile state needed
        # to refresh after a successful scancel. Defer to it.
        target = self.job
        if target.state in {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"}:
            self.notify(
                f"Job {target.job_id} is already {target.state}",
                severity="warning",
                timeout=3,
            )
            return

        from slurmhub.widgets.confirm_screen import ConfirmScreen

        msg = f"Cancel job {target.job_id} ({target.name})?"
        self.app.push_screen(
            ConfirmScreen(msg, dangerous=True, confirm_label="scancel"),
            callback=lambda yes: self._do_scancel(target, yes),
        )

    def _do_scancel(self, job: SlurmJob, confirmed) -> None:
        if not confirmed:
            return
        import shlex

        quoted = shlex.quote(job.job_id)

        def _run() -> None:
            try:
                self.ssh_client.execute(
                    f"scancel {quoted}", timeout=self.ssh_timeout
                )
            except Exception as exc:
                self.app.call_from_thread(
                    self.notify, f"scancel failed: {exc}", severity="error", timeout=5
                )
                return
            self.app.call_from_thread(
                self.notify, f"Cancelled job {job.job_id}", timeout=3
            )

        self.run_worker(_run, thread=True, name=f"detail-scancel-{job.job_id}")

    def action_yank(self) -> None:
        """Copy a job-related value to the clipboard. Cycles through targets."""
        from slurmhub.widgets._clipboard import copy_osc52

        targets = self._yank_targets()
        if not targets:
            return
        label, value = targets[self._yank_idx % len(targets)]
        self._yank_idx += 1
        if copy_osc52(value):
            self.notify(f"Copied {label}: {value}", timeout=2)
        else:
            self.notify(
                f"Clipboard unavailable — {label}: {value}",
                severity="warning",
                timeout=3,
            )

    def action_scroll_down(self) -> None:
        self.query_one("#detail-scroll", ScrollableContainer).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#detail-scroll", ScrollableContainer).scroll_up()

    def action_scroll_home(self) -> None:
        self.query_one("#detail-scroll", ScrollableContainer).scroll_home()

    def action_scroll_end(self) -> None:
        self.query_one("#detail-scroll", ScrollableContainer).scroll_end()
