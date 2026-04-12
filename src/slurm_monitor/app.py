"""Main TUI application for Slurm Monitor."""

import shlex
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header, TabbedContent, TabPane
from textual.worker import Worker, WorkerState

from slurm_monitor.config import AppConfig, ConfigLoader, ProfileConfig
from slurm_monitor.job_aggregator import (
    JobAggregator,
    filter_jobs_by_state,
    sort_jobs_by_time,
)
from slurm_monitor.log_path_resolver import LogPathResolver
from slurm_monitor.squeue_parser import SlurmJob
from slurm_monitor.ssh_wrapper import SSHClient, SSHConnectionError, SSHTimeoutError
from slurm_monitor.widgets.connection_status import ConnectionStatus
from slurm_monitor.widgets.filter_bar import FilterBar
from slurm_monitor.widgets.job_detail import JobDetail
from slurm_monitor.widgets.job_table import JobTable
from slurm_monitor.widgets.status_bar import StatusBar


class ProfileTab:
    """Manages state for a single profile/cluster tab."""

    def __init__(self, profile: ProfileConfig):
        self.profile = profile
        self.ssh_client = SSHClient(profile.ssh)
        self.aggregator = JobAggregator(self.ssh_client, timeout=profile.ssh_timeout)
        self.path_resolver = LogPathResolver(profile.log)
        self.jobs: list[SlurmJob] = []
        self.refresh_in_progress = False
        self._sacct_cache: list[SlurmJob] = []
        self._sacct_last_fetch: float = 0.0

    def close(self) -> None:
        """Clean up SSH connection."""
        self.ssh_client.close()


CSS_PATH = Path(__file__).parent / "app.tcss"


class SlurmMonitorApp(App):
    """Slurm job monitoring TUI application."""

    CSS_PATH = "app.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("?", "help", "Help"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("g", "scroll_home", "Top"),
        ("shift+g", "scroll_end", "Bottom"),
        ("enter", "view_logs", "View Logs"),  # fallback when table not focused
        ("slash", "toggle_filter", "Filter"),
        ("1", "filter_running", "Running"),
        ("2", "filter_pending", "Pending"),
        ("3", "filter_completed", "Completed"),
        ("4", "filter_failed", "Failed"),
        ("0", "filter_all", "All"),
        ("s", "cycle_sort", "Sort"),
    ]

    def __init__(self, config: Optional[AppConfig] = None):
        super().__init__()
        self.config = config or ConfigLoader.load()
        self._profile_tabs: dict[str, ProfileTab] = {}
        self._state_filter = "ALL"
        self._name_filter = ""
        self._sort_mode = "id"  # id, time, state, name

        for name, profile in self.config.profiles.items():
            self._profile_tabs[name] = ProfileTab(profile)

    def compose(self) -> ComposeResult:
        yield Header()

        if len(self._profile_tabs) == 1:
            # Single profile: no tabs needed
            name, tab = next(iter(self._profile_tabs.items()))
            yield ConnectionStatus(id=f"status-{name}")
            yield JobTable(id=f"table-{name}")
            yield JobDetail(id=f"detail-{name}")
        else:
            with TabbedContent():
                for name, tab in self._profile_tabs.items():
                    with TabPane(name, id=f"tab-{name}"):
                        yield ConnectionStatus(id=f"status-{name}")
                        yield JobTable(id=f"table-{name}")
                        yield JobDetail(id=f"detail-{name}")

        yield FilterBar(id="filter-bar")
        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Slurm Job Monitor"

        for name, tab in self._profile_tabs.items():
            status = self.query_one(f"#status-{name}", ConnectionStatus)
            status.host = tab.profile.ssh.host

        # Start periodic refresh for each profile
        for name, tab in self._profile_tabs.items():
            self.set_interval(
                tab.profile.refresh_interval,
                lambda n=name: self._refresh_profile(n),
            )

        # Initial refresh for all profiles
        for name in self._profile_tabs:
            self._refresh_profile(name)

    def _get_active_profile_name(self) -> str:
        """Get the name of the currently active profile tab."""
        if len(self._profile_tabs) == 1:
            return next(iter(self._profile_tabs.keys()))

        tabbed = self.query_one(TabbedContent)
        active_id = tabbed.active
        if active_id and active_id.startswith("tab-"):
            return active_id[4:]
        return next(iter(self._profile_tabs.keys()))

    def _get_active_tab(self) -> ProfileTab:
        """Get the ProfileTab for the currently active tab."""
        return self._profile_tabs[self._get_active_profile_name()]

    def _refresh_profile(self, profile_name: str) -> None:
        """Trigger a job data refresh for a specific profile."""
        tab = self._profile_tabs.get(profile_name)
        if tab is None or tab.refresh_in_progress:
            return

        tab.refresh_in_progress = True
        try:
            status = self.query_one(f"#status-{profile_name}", ConnectionStatus)
            status.is_loading = True
            status.error_message = None
        except Exception:
            pass

        self.run_worker(
            lambda t=tab, n=profile_name: self._fetch_jobs(t, n),
            name=f"fetch-{profile_name}",
            thread=True,
        )

    def _fetch_jobs(
        self, tab: ProfileTab, profile_name: str
    ) -> tuple[str, list[SlurmJob], Optional[str]]:
        """Fetch jobs in a background thread.

        Returns:
            Tuple of (profile_name, jobs, error_message).
            error_message is None on success.
        """
        from slurm_monitor.squeue_parser import fetch_squeue_jobs
        from slurm_monitor.sacct_parser import fetch_sacct_jobs

        try:
            # Always fetch squeue (active jobs)
            active_jobs = fetch_squeue_jobs(
                tab.ssh_client, timeout=tab.profile.ssh_timeout
            )

            # Only re-fetch sacct if cache is stale
            now = time.time()
            if now - tab._sacct_last_fetch > tab.profile.sacct_refresh_interval:
                historical_jobs = fetch_sacct_jobs(
                    tab.ssh_client, timeout=tab.profile.ssh_timeout
                )
                tab._sacct_cache = historical_jobs
                tab._sacct_last_fetch = now
            else:
                historical_jobs = tab._sacct_cache

            from slurm_monitor.job_aggregator import merge_jobs

            merged = merge_jobs(active_jobs, historical_jobs)
            return (profile_name, merged, None)

        except (SSHConnectionError, SSHTimeoutError) as e:
            return (profile_name, [], str(e))

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        worker_name = event.worker.name or ""
        if not worker_name.startswith("fetch-"):
            return

        profile_name = worker_name[6:]  # strip "fetch-"
        tab = self._profile_tabs.get(profile_name)
        if tab is None:
            return

        try:
            status = self.query_one(f"#status-{profile_name}", ConnectionStatus)
        except Exception:
            return

        if event.state == WorkerState.SUCCESS:
            _, jobs, error_msg = event.worker.result
            status.is_loading = False

            if error_msg:
                status.error_message = error_msg
                self.notify(f"Error: {error_msg}", severity="error", timeout=5)
            else:
                tab.jobs = jobs
                status.last_updated = datetime.now().strftime("%H:%M:%S")
                status.error_message = None

                # Only update UI if this is the active tab
                if profile_name == self._get_active_profile_name():
                    self._update_display(profile_name)

            tab.refresh_in_progress = False

        elif event.state == WorkerState.ERROR:
            error = event.worker.error
            status.is_loading = False
            status.error_message = str(error)
            self.notify(f"Error: {error}", severity="error", timeout=5)
            tab.refresh_in_progress = False

        elif event.state == WorkerState.CANCELLED:
            status.is_loading = False
            tab.refresh_in_progress = False

    def _get_filtered_jobs(self, jobs: list[SlurmJob]) -> list[SlurmJob]:
        """Apply current filters and sorting to a job list."""
        filtered = jobs

        if self._state_filter != "ALL":
            filtered = filter_jobs_by_state(filtered, [self._state_filter])

        if self._name_filter:
            query = self._name_filter.lower()
            filtered = [
                j for j in filtered
                if query in j.name.lower() or query in j.job_id
            ]

        if self._sort_mode == "time":
            filtered = sort_jobs_by_time(filtered)
        elif self._sort_mode == "name":
            filtered = sorted(filtered, key=lambda j: j.name.lower())
        elif self._sort_mode == "state":
            filtered = sorted(filtered, key=lambda j: j.state)
        # "id" is the default (already sorted by merge_jobs)

        return filtered

    def _update_display(self, profile_name: str) -> None:
        """Update the UI for a specific profile."""
        tab = self._profile_tabs.get(profile_name)
        if tab is None:
            return

        filtered = self._get_filtered_jobs(tab.jobs)

        try:
            table = self.query_one(f"#table-{profile_name}", JobTable)
            table.update_jobs(filtered)
        except Exception:
            pass

        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.update_stats(
                tab.jobs,
                filter_text=self._name_filter,
                state_filter=self._state_filter,
            )
        except Exception:
            pass

    def on_data_table_row_selected(self, event) -> None:
        """Handle Enter key on a table row — view logs for that job."""
        self.action_view_logs()

    def on_data_table_cursor_moved(self, event) -> None:
        """Update job detail panel when cursor moves."""
        active_name = self._get_active_profile_name()
        tab = self._profile_tabs.get(active_name)
        if tab is None:
            return

        filtered = self._get_filtered_jobs(tab.jobs)

        try:
            table = self.query_one(f"#table-{active_name}", JobTable)
            detail = self.query_one(f"#detail-{active_name}", JobDetail)
        except Exception:
            return

        if table.cursor_row is not None and 0 <= table.cursor_row < len(filtered):
            job = filtered[table.cursor_row]
            log_path = tab.path_resolver.resolve_path(
                job_id=job.job_id, work_dir=job.work_dir
            )
            detail.set_job(job, log_path)
        else:
            detail.set_job(None)

    def on_tabbed_content_tab_activated(self, event) -> None:
        """Refresh display when switching tabs."""
        active_name = self._get_active_profile_name()
        self._update_display(active_name)

    # ── Actions ──────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        """Manually refresh the active profile."""
        name = self._get_active_profile_name()
        tab = self._profile_tabs.get(name)
        if tab:
            tab._sacct_last_fetch = 0.0  # force sacct re-fetch
        self.notify("Refreshing...", timeout=2)
        self._refresh_profile(name)

    def action_help(self) -> None:
        active = self._get_active_tab()
        help_text = (
            "Slurm Job Monitor - Help\n\n"
            "q: Quit  r: Refresh  ?: Help\n"
            "j/k: Navigate  g/G: Top/Bottom\n"
            "Enter: View logs  /: Search\n"
            "1: Running  2: Pending  3: Completed  4: Failed  0: All\n"
            "s: Cycle sort (id/time/name/state)\n"
            f"\nRefresh: {active.profile.refresh_interval}s  "
            f"Sacct cache: {active.profile.sacct_refresh_interval}s"
        )
        self.notify(help_text, timeout=10)

    def action_cursor_down(self) -> None:
        name = self._get_active_profile_name()
        try:
            self.query_one(f"#table-{name}", JobTable).action_cursor_down()
        except Exception:
            pass

    def action_cursor_up(self) -> None:
        name = self._get_active_profile_name()
        try:
            self.query_one(f"#table-{name}", JobTable).action_cursor_up()
        except Exception:
            pass

    def action_scroll_home(self) -> None:
        name = self._get_active_profile_name()
        try:
            self.query_one(f"#table-{name}", JobTable).action_scroll_home()
        except Exception:
            pass

    def action_scroll_end(self) -> None:
        name = self._get_active_profile_name()
        try:
            self.query_one(f"#table-{name}", JobTable).action_scroll_end()
        except Exception:
            pass

    def action_view_logs(self) -> None:
        """View logs for the selected job."""
        name = self._get_active_profile_name()
        tab = self._profile_tabs.get(name)
        if tab is None:
            return

        try:
            table = self.query_one(f"#table-{name}", JobTable)
        except Exception:
            return

        filtered = self._get_filtered_jobs(tab.jobs)

        if table.cursor_row is None or table.cursor_row < 0:
            self.notify("No job selected", severity="warning", timeout=3)
            return

        if not filtered:
            self.notify("No jobs available", severity="warning", timeout=3)
            return

        try:
            selected_job = filtered[table.cursor_row]
        except IndexError:
            self.notify("Invalid job selection", severity="error", timeout=3)
            return

        log_path = tab.path_resolver.resolve_path(
            job_id=selected_job.job_id,
            work_dir=selected_job.work_dir,
        )

        if "{" in log_path:
            self.notify(
                f"Cannot resolve log path: {log_path}",
                severity="error",
                timeout=5,
            )
            return

        view_cmd = tab.path_resolver.resolve_view_command(
            job_id=selected_job.job_id,
            work_dir=selected_job.work_dir,
        )

        self._run_log_viewer(selected_job, log_path, view_cmd, tab)

    def _run_log_viewer(
        self, job: SlurmJob, log_path: str, view_cmd: str, tab: ProfileTab
    ) -> None:
        """Suspend app and run the log viewer command via SSH."""
        with self.suspend():
            ssh_cmd = [
                "ssh",
                "-t",
                tab.profile.ssh.host,
                view_cmd,
            ]

            # Add SSH options
            if tab.profile.ssh.port != 22:
                ssh_cmd.insert(2, "-p")
                ssh_cmd.insert(3, str(tab.profile.ssh.port))
            if tab.profile.ssh.username:
                ssh_cmd.insert(2, "-l")
                ssh_cmd.insert(3, tab.profile.ssh.username)
            if tab.profile.ssh.jump_host:
                ssh_cmd.insert(2, "-J")
                ssh_cmd.insert(3, tab.profile.ssh.jump_host)

            try:
                print(f"\nViewing logs for job {job.job_id}: {job.name}")
                print(f"Log file: {log_path}")
                print(f"Host: {tab.profile.ssh.host}")
                print(f"Command: {view_cmd}")
                print(f"\nPress Ctrl+C to return to the monitor\n")
                print("-" * 60)

                subprocess.run(ssh_cmd)

            except FileNotFoundError:
                print("\nError: SSH command not found")
            except KeyboardInterrupt:
                print("\n\nReturning to monitor...")
            except Exception as e:
                print(f"\nError: {e}")

            input("\nPress Enter to continue...")

        self.notify("Returned from log viewer. Refreshing...", timeout=2)
        self._refresh_profile(self._get_active_profile_name())

    # ── Filter actions ───────────────────────────────────────────────

    def action_toggle_filter(self) -> None:
        """Toggle the search/filter bar."""
        filter_bar = self.query_one("#filter-bar", FilterBar)
        if filter_bar.display:
            filter_bar.hide()
        else:
            filter_bar.show()

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        self._name_filter = event.value
        name = self._get_active_profile_name()
        self._update_display(name)

    def on_filter_bar_filter_closed(self, event: FilterBar.FilterClosed) -> None:
        # Return focus to the table
        name = self._get_active_profile_name()
        try:
            self.query_one(f"#table-{name}", JobTable).focus()
        except Exception:
            pass

    def _set_state_filter(self, state: str) -> None:
        self._state_filter = state
        name = self._get_active_profile_name()
        self._update_display(name)

    def action_filter_running(self) -> None:
        self._set_state_filter("RUNNING" if self._state_filter != "RUNNING" else "ALL")

    def action_filter_pending(self) -> None:
        self._set_state_filter("PENDING" if self._state_filter != "PENDING" else "ALL")

    def action_filter_completed(self) -> None:
        self._set_state_filter("COMPLETED" if self._state_filter != "COMPLETED" else "ALL")

    def action_filter_failed(self) -> None:
        self._set_state_filter("FAILED" if self._state_filter != "FAILED" else "ALL")

    def action_filter_all(self) -> None:
        self._set_state_filter("ALL")

    def action_cycle_sort(self) -> None:
        modes = ["id", "time", "name", "state"]
        current = modes.index(self._sort_mode) if self._sort_mode in modes else 0
        self._sort_mode = modes[(current + 1) % len(modes)]
        self.notify(f"Sort: {self._sort_mode}", timeout=2)
        name = self._get_active_profile_name()
        self._update_display(name)

    def on_unmount(self) -> None:
        """Clean up SSH connections on exit."""
        for tab in self._profile_tabs.values():
            tab.close()
