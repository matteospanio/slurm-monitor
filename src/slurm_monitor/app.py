"""Main TUI application for Slurm Monitor."""

import subprocess
from datetime import datetime
from typing import Optional

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, Label, Static

from slurm_monitor.config import Config, ConfigLoader
from slurm_monitor.job_aggregator import JobAggregator
from slurm_monitor.log_path_resolver import LogPathResolver
from slurm_monitor.squeue_parser import SlurmJob


class ConnectionStatus(Static):
    """Widget displaying connection status and information."""

    host: reactive[str] = reactive("localhost")
    last_updated: reactive[Optional[str]] = reactive(None)
    is_loading: reactive[bool] = reactive(False)
    error_message: reactive[Optional[str]] = reactive(None)

    def render(self) -> Text:
        """Render the connection status."""
        text = Text()

        # Connection info
        text.append("📡 ", style="bold")
        text.append("Host: ", style="dim")
        text.append(self.host, style="bold cyan")
        text.append(" | ")

        # Last updated
        if self.is_loading:
            text.append("⟳ ", style="bold yellow")
            text.append("Updating...", style="yellow")
        elif self.error_message:
            text.append("❌ ", style="bold red")
            text.append(f"Error: {self.error_message}", style="red")
        elif self.last_updated:
            text.append("✓ ", style="bold green")
            text.append("Updated: ", style="dim")
            text.append(self.last_updated, style="green")
        else:
            text.append("⏸ ", style="dim")
            text.append("Not connected", style="dim")

        return text


class JobTable(DataTable):
    """DataTable widget for displaying Slurm jobs."""

    COLUMN_KEYS = ["job_id", "name", "state", "time", "work_dir"]

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

        # Add columns
        self.add_column("Job ID", key="job_id")
        self.add_column("Name", key="name")
        self.add_column("State", key="state")
        self.add_column("Time", key="time")
        self.add_column("Work Dir", key="work_dir")

    def update_jobs(self, jobs: list[SlurmJob]) -> None:
        """
        Update table with new job data.

        Args:
            jobs: List of SlurmJob objects to display
        """
        # Clear existing rows
        self.clear()

        # Add rows for each job
        for job in jobs:
            # Style the state with color
            state_style = self.STATE_COLORS.get(job.state, "white")
            styled_state = Text(job.state, style=f"bold {state_style}")

            # Add row
            self.add_row(
                job.job_id,
                job.name,
                styled_state,
                job.time,
                job.work_dir or "",
                key=job.job_id,
            )


class SlurmMonitorApp(App):
    """Slurm job monitoring TUI application."""

    CSS = """
    ConnectionStatus {
        dock: top;
        height: 1;
        background: $surface;
        padding: 0 1;
    }

    JobTable {
        height: 1fr;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("?", "help", "Help"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("g", "scroll_home", "Top"),
        ("G", "scroll_end", "Bottom"),
        ("enter", "view_logs", "View Logs"),
    ]

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the application.

        Args:
            config: Optional Config object. If None, loads from default location.
        """
        super().__init__()
        self.config = config or ConfigLoader.load()
        self.aggregator = JobAggregator(
            self.config.remote_host,
            timeout=self.config.ssh_timeout,
        )
        self.path_resolver = LogPathResolver(self.config)
        self.jobs: list[SlurmJob] = []

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield ConnectionStatus(id="connection-status")
        yield JobTable(id="job-table")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the application after mounting."""
        # Set initial connection status
        status = self.query_one(ConnectionStatus)
        status.host = self.config.remote_host

        # Set the app title
        self.title = "Slurm Job Monitor"
        self.sub_title = f"{self.config.remote_host}"

        # Start periodic refresh
        self.set_interval(
            self.config.refresh_interval,
            self.refresh_data,
        )

        # Initial data load
        self.refresh_data()

    async def refresh_data(self) -> None:
        """Fetch and update job data."""
        status = self.query_one(ConnectionStatus)
        table = self.query_one(JobTable)

        try:
            # Set loading state
            status.is_loading = True
            status.error_message = None

            # Fetch jobs (run in thread to not block UI)
            jobs = await self.run_in_thread(self._fetch_jobs)

            # Update state
            self.jobs = jobs
            status.is_loading = False
            status.last_updated = datetime.now().strftime("%H:%M:%S")

            # Update table
            table.update_jobs(jobs)

        except Exception as e:
            status.is_loading = False
            status.error_message = str(e)
            self.notify(f"Error fetching jobs: {e}", severity="error", timeout=5)

    def _fetch_jobs(self) -> list[SlurmJob]:
        """
        Fetch jobs from the aggregator.

        Returns:
            List of SlurmJob objects
        """
        return self.aggregator.fetch_all_jobs()

    def action_refresh(self) -> None:
        """Manually refresh the job data."""
        self.notify("Refreshing job data...", timeout=2)
        self.refresh_data()

    def action_help(self) -> None:
        """Show help information."""
        help_text = """
        Slurm Job Monitor - Help

        Keybindings:
        - q: Quit application
        - r: Manually refresh data
        - j/k: Navigate down/up (Vim-style)
        - g/G: Jump to top/bottom
        - Enter: View job logs (tail -f)
        - ↑/↓: Navigate jobs (arrow keys)
        - ?: Show this help

        The display updates automatically every {} seconds.
        """.format(self.config.refresh_interval)

        self.notify(help_text.strip(), timeout=10)

    def action_cursor_down(self) -> None:
        """Move cursor down (Vim j key)."""
        table = self.query_one(JobTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up (Vim k key)."""
        table = self.query_one(JobTable)
        table.action_cursor_up()

    def action_scroll_home(self) -> None:
        """Scroll to top (Vim g key)."""
        table = self.query_one(JobTable)
        table.action_scroll_home()

    def action_scroll_end(self) -> None:
        """Scroll to bottom (Vim G key)."""
        table = self.query_one(JobTable)
        table.action_scroll_end()

    def action_view_logs(self) -> None:
        """View logs for the selected job using tail -f."""
        table = self.query_one(JobTable)

        # Get the selected job
        if table.cursor_row is None or table.cursor_row < 0:
            self.notify("No job selected", severity="warning", timeout=3)
            return

        if not self.jobs:
            self.notify("No jobs available", severity="warning", timeout=3)
            return

        # Find the selected job
        try:
            selected_job = self.jobs[table.cursor_row]
        except IndexError:
            self.notify("Invalid job selection", severity="error", timeout=3)
            return

        # Resolve log path
        log_path = self.path_resolver.resolve_path(
            job_id=selected_job.job_id,
            work_dir=selected_job.work_dir,
        )

        # Check if path contains unresolved tokens
        if "{" in log_path:
            self.notify(
                f"Cannot resolve log path: {log_path}",
                severity="error",
                timeout=5,
            )
            return

        # Suspend the app and run tail
        self._tail_log_file(selected_job, log_path)

    def _tail_log_file(self, job: SlurmJob, log_path: str) -> None:
        """
        Suspend app and tail the log file via SSH.

        Args:
            job: The SlurmJob to view logs for
            log_path: Resolved path to the log file
        """
        with self.suspend():
            # Build SSH tail command
            ssh_cmd = [
                "ssh",
                "-t",
                self.config.remote_host,
                f"tail -f {log_path}",
            ]

            try:
                # Show info before launching
                print(f"\n📄 Viewing logs for job {job.job_id}: {job.name}")
                print(f"📁 Log file: {log_path}")
                print(f"🔗 Host: {self.config.remote_host}")
                print("\n🛈  Press Ctrl+C to return to the monitor\n")
                print("-" * 60)

                # Run SSH tail command
                subprocess.run(ssh_cmd)

            except FileNotFoundError:
                print("\n❌ Error: SSH command not found")
                print("   Please ensure SSH is installed and in your PATH")
            except KeyboardInterrupt:
                print("\n\n✓ Returning to monitor...")
            except Exception as e:
                print(f"\n❌ Error: {e}")

            # Wait for user to see any error messages
            input("\nPress Enter to continue...")

        # Refresh data after returning
        self.notify("Returned from log viewer. Refreshing...", timeout=2)
        self.refresh_data()


def main(config: Optional[Config] = None) -> None:
    """
    Run the Slurm Monitor application.

    Args:
        config: Optional Config object. If None, loads from default location.
    """
    app = SlurmMonitorApp(config)
    app.run()


if __name__ == "__main__":
    main()
