"""Job history & analytics screen.

Full-screen view (opened with ``H``) over the persisted job-history database.
Two modes, toggled with ``a``:

* **Past runs** — a filterable/searchable table of recorded runs (state, date
  range, favourites, current-profile vs all-profiles scope).
* **Usage aggregates** — GPU-/CPU-/memory-hours consumed over the selected
  range, with a per-profile breakdown when viewing all profiles.

Reads run on a worker thread (mirroring ``ClusterDashboardScreen``); favourite
and note writes also go through workers so the UI thread never blocks on the DB.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static

from slurmhub.db.models import utcnow
from slurmhub.slurm.scontrol import format_mem_human
from slurmhub.slurm.squeue import SlurmJob
from slurmhub.tui.widgets.filter_bar import FilterBar
from slurmhub.tui.widgets.job_table import JobTable

if TYPE_CHECKING:
    from slurmhub.db import Database, JobRun, Repository
    from slurmhub.slurm.ssh import SSHClient

_DATE_RANGES = [
    ("all", "All time", None),
    ("24h", "Last 24h", 1),
    ("7d", "Last 7 days", 7),
    ("30d", "Last 30 days", 30),
]
_STATE_FILTERS = {
    "1": ("RUNNING", ["RUNNING"]),
    "2": ("PENDING", ["PENDING"]),
    "3": ("COMPLETED", ["COMPLETED"]),
    "4": ("FAILED", ["FAILED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL"]),
}


def _fmt_elapsed(secs: Optional[int]) -> str:
    if not secs:
        return "" if secs is None else "0:00"
    hours, rem = divmod(secs, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _fmt_mem(mb: Optional[int]) -> str:
    if not mb:
        return ""
    return format_mem_human(mb * 1024 * 1024)


def _fmt_gpu(count: Optional[int], gpu_type: Optional[str]) -> str:
    if not count:
        return ""
    return f"{count}x {gpu_type}" if gpu_type else str(count)


class HistoryHeader(Static):
    """Header bar across the top of the history screen."""


class HistoryScreen(Screen):
    """Full-screen browser over the persisted job history."""

    BINDINGS = [
        Binding("escape", "close", "Back", priority=True),
        Binding("q", "close", "Back"),
        Binding("a", "toggle_aggregates", "Aggregates"),
        Binding("p", "toggle_scope", "Profile/All"),
        Binding("t", "cycle_range", "Date range"),
        Binding("F,shift+f", "toggle_favourites", "Favourites"),
        Binding("f", "favourite_row", "★ Favourite"),
        Binding("n", "note_row", "Note"),
        Binding("slash", "search", "Search"),
        Binding("0", "filter_all", "All states"),
        Binding("1", "filter_running", "Running"),
        Binding("2", "filter_pending", "Pending"),
        Binding("3", "filter_completed", "Completed"),
        Binding("4", "filter_failed", "Failed"),
        Binding("enter", "open_detail", "Details"),
        Binding("r", "refresh", "Refresh"),
        Binding("question_mark", "help", "Help"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "cursor_top", "Top", show=False),
        Binding("G,shift+g", "cursor_bottom", "Bottom", show=False),
    ]

    CSS = """
    HistoryHeader {
        dock: top;
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 1;
    }

    #history-scroll {
        height: 1fr;
    }

    #history-table {
        height: auto;
    }

    #history-aggregates {
        padding: 1 2;
    }
    """

    def __init__(
        self,
        database: "Database",
        repository: "Repository",
        profile_name: str,
        profile_names: list[str],
        ssh_client: "Optional[SSHClient]" = None,
        ssh_timeout: int = 10,
    ) -> None:
        super().__init__()
        self.database = database
        self.repository = repository
        self.profile_name = profile_name
        self.profile_names = profile_names
        self.ssh_client = ssh_client
        self.ssh_timeout = ssh_timeout

        self.mode = "list"  # or "aggregates"
        self.scope_all = False
        self.state_label = "ALL"
        self.state_values: Optional[list[str]] = None
        self.favourites_only = False
        self.range_idx = 0
        self.search = ""

        self.runs: list[JobRun] = []
        self._query_in_progress = False

    # ── Layout ──────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield HistoryHeader(self._header_text(), id="history-header")
        with ScrollableContainer(id="history-scroll"):
            yield DataTable(id="history-table")
            yield Static(id="history-aggregates")
        yield FilterBar(id="history-filter")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns(
            "★", "Profile", "Job ID", "Name", "State", "Submit",
            "Elapsed", "CPU", "GPU", "Mem", "Note",
        )
        self.query_one("#history-aggregates", Static).display = False
        self._kick_query()

    # ── Query (worker thread) ────────────────────────────────────────────

    def _since(self):
        days = _DATE_RANGES[self.range_idx][2]
        return utcnow() - timedelta(days=days) if days else None

    def _kick_query(self) -> None:
        if self._query_in_progress:
            return
        self._query_in_progress = True
        self._set_header(loading=True)
        self.run_worker(self._query, thread=True, exclusive=True, name="hist-query")

    def _query(self):
        profile = None if self.scope_all else self.profile_name
        since = self._since()
        with self.database.session() as session:
            runs = self.repository.query_runs(
                session,
                profile=profile,
                states=self.state_values,
                since=since,
                favourites_only=self.favourites_only,
                search=self.search or None,
                limit=500,
            )
            totals = self.repository.aggregate_usage(
                session, profile=profile, since=since
            )
        return runs, totals

    def on_worker_state_changed(self, event) -> None:
        from textual.worker import WorkerState

        if (event.worker.name or "") != "hist-query":
            return
        if event.state in (WorkerState.SUCCESS, WorkerState.ERROR):
            self._query_in_progress = False
        if event.state != WorkerState.SUCCESS:
            self._set_header(loading=False)
            return
        self.runs, self._totals = event.worker.result
        self._refresh_view()

    # ── Rendering ─────────────────────────────────────────────────────────

    def _header_text(self, loading: bool = False) -> str:
        scope = "all profiles" if self.scope_all else self.profile_name
        rng = _DATE_RANGES[self.range_idx][1]
        bits = [f"History · {scope}", _DATE_RANGES[self.range_idx][1] and rng]
        flags = []
        if self.state_label != "ALL":
            flags.append(self.state_label)
        if self.favourites_only:
            flags.append("★ only")
        if self.search:
            flags.append(f"/{self.search}")
        mode = "aggregates" if self.mode == "aggregates" else f"{len(self.runs)} runs"
        suffix = " · loading…" if loading else ""
        flag_str = f" │ {', '.join(flags)}" if flags else ""
        return f" {bits[0]} │ {rng} │ {mode}{flag_str}{suffix}"

    def _set_header(self, *, loading: bool) -> None:
        try:
            self.query_one("#history-header", HistoryHeader).update(
                self._header_text(loading=loading)
            )
        except Exception:
            pass

    def _refresh_view(self) -> None:
        table = self.query_one("#history-table", DataTable)
        aggregates = self.query_one("#history-aggregates", Static)
        if self.mode == "aggregates":
            table.display = False
            aggregates.display = True
            self._render_aggregates(aggregates)
        else:
            aggregates.display = False
            table.display = True
            self._render_table(table)
        self._set_header(loading=False)

    def _render_table(self, table: DataTable) -> None:
        table.clear()
        for run in self.runs:
            state_style = JobTable.STATE_COLORS.get(run.state, "white")
            table.add_row(
                Text("★", style="bold yellow") if run.favourite else Text(""),
                run.profile_name,
                run.job_id,
                run.name,
                Text(run.state, style=f"bold {state_style}"),
                run.submit_time or "",
                Text(_fmt_elapsed(run.elapsed_seconds), justify="right"),
                str(run.num_cpus) if run.num_cpus else "",
                Text(_fmt_gpu(run.gpu_count, run.gpu_type), style="cyan"),
                _fmt_mem(run.mem_requested_mb),
                Text(run.note or "", style="italic"),
            )
        if self.runs:
            table.move_cursor(row=0, animate=False)

    def _render_aggregates(self, body: Static) -> None:
        totals = getattr(self, "_totals", None)
        text = Text()
        scope = "all profiles" if self.scope_all else self.profile_name
        text.append(f"Resource usage — {scope}\n", style="bold underline")
        text.append(f"({_DATE_RANGES[self.range_idx][1]})\n\n", style="dim")
        if totals is None or totals.job_count == 0:
            text.append("No runs in this range.\n", style="dim italic")
            body.update(text)
            return

        text.append("  Runs:        ", style="dim")
        text.append(f"{totals.job_count}\n")
        text.append("  GPU-hours:   ", style="dim")
        text.append(f"{totals.gpu_hours:,.1f}\n", style="cyan")
        text.append("  CPU-hours:   ", style="dim")
        text.append(f"{totals.cpu_hours:,.1f}\n")
        text.append("  Memory:      ", style="dim")
        text.append(f"{totals.mem_gb_hours:,.1f} GB·h\n")
        if totals.avg_gpu_util is not None:
            text.append("  Avg GPU util:", style="dim")
            text.append(f" {totals.avg_gpu_util:.0f}%  ", style="dim")
            text.append("(measured)\n", style="dim italic")

        if totals.per_profile:
            text.append("\nPer profile\n", style="bold underline")
            text.append(
                f"  {'profile':<16}{'runs':>6}{'gpu·h':>12}"
                f"{'cpu·h':>12}{'GB·h':>14}\n",
                style="dim",
            )
            for p in totals.per_profile:
                text.append(
                    f"  {p.profile_name:<16}{p.job_count:>6}"
                    f"{p.gpu_hours:>12,.1f}{p.cpu_hours:>12,.1f}"
                    f"{p.mem_gb_hours:>14,.1f}\n"
                )
        body.update(text)

    # ── Cursor / current row ──────────────────────────────────────────────

    def _current_run(self) -> "Optional[JobRun]":
        if self.mode != "list" or not self.runs:
            return None
        table = self.query_one("#history-table", DataTable)
        row = table.cursor_row
        if row is None or not (0 <= row < len(self.runs)):
            return None
        return self.runs[row]

    # ── Actions ─────────────────────────────────────────────────────────

    def action_close(self) -> None:
        self.app.pop_screen()

    def action_refresh(self) -> None:
        self._kick_query()

    def action_help(self) -> None:
        from slurmhub.tui.widgets.help_screen import HelpScreen

        self.app.push_screen(HelpScreen(context="history"))

    def action_toggle_aggregates(self) -> None:
        self.mode = "aggregates" if self.mode == "list" else "list"
        self._refresh_view()

    def action_toggle_scope(self) -> None:
        self.scope_all = not self.scope_all
        self._kick_query()

    def action_cycle_range(self) -> None:
        self.range_idx = (self.range_idx + 1) % len(_DATE_RANGES)
        self._kick_query()

    def action_toggle_favourites(self) -> None:
        self.favourites_only = not self.favourites_only
        self._kick_query()

    def _set_state_filter(self, label: str, values: Optional[list[str]]) -> None:
        self.state_label = label
        self.state_values = values
        self._kick_query()

    def action_filter_all(self) -> None:
        self._set_state_filter("ALL", None)

    def action_filter_running(self) -> None:
        self._set_state_filter(*_state_arg("1", self.state_label))

    def action_filter_pending(self) -> None:
        self._set_state_filter(*_state_arg("2", self.state_label))

    def action_filter_completed(self) -> None:
        self._set_state_filter(*_state_arg("3", self.state_label))

    def action_filter_failed(self) -> None:
        self._set_state_filter(*_state_arg("4", self.state_label))

    def action_search(self) -> None:
        self.query_one("#history-filter", FilterBar).show(initial_value=self.search)

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        self.search = event.value
        self._kick_query()

    def on_filter_bar_filter_closed(self, event: FilterBar.FilterClosed) -> None:
        try:
            self.query_one("#history-table", DataTable).focus()
        except Exception:
            pass

    def action_cursor_down(self) -> None:
        self.query_one("#history-table", DataTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#history-table", DataTable).action_cursor_up()

    def action_cursor_top(self) -> None:
        if self.runs:
            self.query_one("#history-table", DataTable).move_cursor(
                row=0, animate=False
            )

    def action_cursor_bottom(self) -> None:
        if self.runs:
            self.query_one("#history-table", DataTable).move_cursor(
                row=len(self.runs) - 1, animate=False
            )

    def action_favourite_row(self) -> None:
        run = self._current_run()
        if run is None:
            return
        target = not run.favourite

        def _run() -> None:
            try:
                with self.database.session() as session:
                    self.repository.set_favourite(session, run.pk, target)
            except Exception as exc:
                self.app.call_from_thread(
                    self.notify, f"Favourite failed: {exc}", severity="error", timeout=4
                )
                return
            self.app.call_from_thread(self._kick_query)

        self.run_worker(_run, thread=True, name=f"hist-fav-{run.pk}")

    def action_note_row(self) -> None:
        run = self._current_run()
        if run is None:
            return
        from slurmhub.tui.widgets.note_input_screen import NoteInputScreen

        self.app.push_screen(
            NoteInputScreen(run.job_id, initial=run.note or ""),
            callback=lambda note, pk=run.pk: self._save_note(pk, note),
        )

    def _save_note(self, job_pk: int, note: Optional[str]) -> None:
        if note is None:
            return

        def _run() -> None:
            try:
                with self.database.session() as session:
                    self.repository.set_note(session, job_pk, note)
            except Exception as exc:
                self.app.call_from_thread(
                    self.notify, f"Note failed: {exc}", severity="error", timeout=4
                )
                return
            self.app.call_from_thread(self._kick_query)

        self.run_worker(_run, thread=True, name=f"hist-fav-{job_pk}")

    def action_open_detail(self) -> None:
        run = self._current_run()
        if run is None or self.ssh_client is None:
            return
        from slurmhub.tui.widgets.job_detail_screen import JobDetailScreen

        job = SlurmJob(
            job_id=run.job_id,
            name=run.name,
            state=run.state,
            time=_fmt_elapsed(run.elapsed_seconds),
            work_dir=run.work_dir,
            submit_time=run.submit_time or None,
            num_cpus=run.num_cpus,
            mem_requested_mb=run.mem_requested_mb,
        )
        self.app.push_screen(
            JobDetailScreen(
                job,
                self.ssh_client,
                self.ssh_timeout,
                repository=self.repository,
                database=self.database,
                profile_name=run.profile_name,
            )
        )


def _state_arg(key: str, current_label: str) -> tuple[str, Optional[list[str]]]:
    """Toggle a state filter: pressing its key again clears back to ALL."""
    label, values = _STATE_FILTERS[key]
    if current_label == label:
        return "ALL", None
    return label, values
