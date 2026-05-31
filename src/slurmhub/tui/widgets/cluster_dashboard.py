"""Cluster dashboard screen.

Full-screen view triggered by the ``d`` key. Shows cluster-wide capacity
bars (CPUs/GPUs/Memory), a per-partition summary table, and a scrollable
per-node table. Re-fetches ``sinfo`` every 60s while open.
"""

from datetime import datetime
from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static

from slurmhub.slurm.scontrol import format_mem_human
from slurmhub.slurm.sinfo import (
    ClusterCapacity,
    NodeStats,
    PartitionStats,
    fetch_sinfo,
)
from slurmhub.slurm.ssh import SSHClient
from slurmhub.tui.widgets._bars import render_bar

# How long cached sinfo data is considered fresh enough to skip a fetch.
SINFO_REFRESH_SECONDS = 60.0

# Color palette for node states. Reused for partition state counts too.
_NODE_STATE_COLORS = {
    "idle": "green",
    "mixed": "yellow",
    "allocated": "blue",
    "alloc": "blue",
    "completing": "cyan",
    "drain": "magenta",
    "drained": "magenta",
    "draining": "magenta",
    "down": "red",
    "fail": "red",
    "failing": "red",
    "maint": "magenta",
    "reserved": "cyan",
}


def _format_mem_mb(mem_mb: int) -> str:
    """Render a megabyte value as e.g. ``512G``."""
    if mem_mb <= 0:
        return "-"
    return format_mem_human(mem_mb * 1024 * 1024)


def _state_text(state: str) -> Text:
    color = _NODE_STATE_COLORS.get(state, "white")
    return Text(state, style=f"bold {color}")


class DashboardHeader(Static):
    """Header bar across the top of the dashboard screen."""


class DashboardBody(Static):
    """Capacity bars block below the header."""


class ClusterDashboardScreen(Screen):
    """Full-screen cluster overview."""

    BINDINGS = [
        Binding("escape", "close", "Back", priority=True),
        Binding("q", "close", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("question_mark", "help", "Help"),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("g", "scroll_home", "Top", show=False),
        Binding("G,shift+g", "scroll_end", "Bottom", show=False),
    ]

    CSS = """
    DashboardHeader {
        dock: top;
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 1;
    }

    #dashboard-scroll {
        height: 1fr;
    }

    DashboardBody {
        padding: 1 2;
    }

    #partition-table {
        margin: 1 2;
        height: auto;
        max-height: 12;
    }

    #node-table {
        margin: 1 2;
        height: auto;
    }
    """

    def __init__(
        self,
        profile_name: str,
        ssh_client: SSHClient,
        ssh_timeout: int = 10,
        initial_capacity: Optional[ClusterCapacity] = None,
        initial_partitions: Optional[list[PartitionStats]] = None,
        initial_nodes: Optional[list[NodeStats]] = None,
    ) -> None:
        super().__init__()
        self.profile_name = profile_name
        self.ssh_client = ssh_client
        self.ssh_timeout = ssh_timeout
        self.capacity: Optional[ClusterCapacity] = initial_capacity
        self.partitions: list[PartitionStats] = initial_partitions or []
        self.nodes: list[NodeStats] = initial_nodes or []
        self._refresh_in_progress = False

    # ── Layout ──────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield DashboardHeader(self._header_text(), id="dashboard-header")
        with ScrollableContainer(id="dashboard-scroll"):
            yield DashboardBody(id="capacity-block")
            yield DataTable(id="partition-table")
            yield DataTable(id="node-table")
        yield Footer()

    def on_mount(self) -> None:
        partition_table = self.query_one("#partition-table", DataTable)
        partition_table.cursor_type = "none"
        partition_table.zebra_stripes = True
        partition_table.add_columns(
            "Partition", "Nodes (i/m/a/d)", "CPUs (free/total)",
            "GPUs (used/total)", "Mem total", "Up",
        )

        node_table = self.query_one("#node-table", DataTable)
        node_table.cursor_type = "row"
        node_table.zebra_stripes = True
        node_table.add_columns(
            "Node", "Partition", "State", "CPUs (alloc/total)",
            "Memory (free/total)", "GPUs (used/total)", "Reason",
        )

        # Paint whatever cached data we already have, then trigger a refresh
        # only if it's stale (or absent).
        self._render_all()

        if self._needs_refresh():
            self._kick_refresh()

        self.set_interval(SINFO_REFRESH_SECONDS, self._kick_refresh)

    # ── Data refresh ────────────────────────────────────────────────────

    def _needs_refresh(self) -> bool:
        if self.capacity is None:
            return True
        # We don't keep a precise fetched-at timestamp on the screen, so
        # always allow a kick on first mount; the interval handles the rest.
        return False

    def _kick_refresh(self) -> None:
        if self._refresh_in_progress:
            return
        self._refresh_in_progress = True
        self._set_header(loading=True)
        self.run_worker(self._fetch, thread=True, exclusive=True)

    def _fetch(self) -> Optional[
        tuple[ClusterCapacity, list[PartitionStats], list[NodeStats]]
    ]:
        try:
            return fetch_sinfo(self.ssh_client, self.ssh_timeout)
        except Exception as exc:  # noqa: BLE001 — surfaced via notify
            self.app.call_from_thread(
                self.notify, f"sinfo failed: {exc}",
                severity="error", timeout=5,
            )
            return None

    def on_worker_state_changed(self, event) -> None:
        from textual.worker import WorkerState

        if event.state in (WorkerState.SUCCESS, WorkerState.ERROR):
            self._refresh_in_progress = False

        if event.state != WorkerState.SUCCESS:
            self._set_header(loading=False)
            return

        result = event.worker.result
        if result is None:
            self._set_header(loading=False)
            return

        capacity, partitions, nodes = result
        self.capacity = capacity
        self.partitions = partitions
        self.nodes = nodes
        self._render_all()

        # Also stash the freshly fetched data back on the owning ProfileTab
        # so re-opening the screen is instant. ``app`` is the main
        # SlurmhubApp; look up the tab by profile name.
        tab = getattr(self.app, "_profile_tabs", {}).get(self.profile_name)
        if tab is not None:
            import time
            tab.cluster_capacity = capacity
            tab.partitions = partitions
            tab.nodes = nodes
            tab._sinfo_last_fetch = time.time()

    # ── Actions ─────────────────────────────────────────────────────────

    def action_close(self) -> None:
        self.app.pop_screen()

    def action_refresh(self) -> None:
        self._kick_refresh()

    def action_help(self) -> None:
        from slurmhub.tui.widgets.help_screen import HelpScreen

        self.app.push_screen(HelpScreen(context="dashboard"))

    def action_scroll_down(self) -> None:
        self.query_one("#dashboard-scroll", ScrollableContainer).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#dashboard-scroll", ScrollableContainer).scroll_up()

    def action_scroll_home(self) -> None:
        self.query_one("#dashboard-scroll", ScrollableContainer).scroll_home()

    def action_scroll_end(self) -> None:
        self.query_one("#dashboard-scroll", ScrollableContainer).scroll_end()

    # ── Rendering helpers ───────────────────────────────────────────────

    def _header_text(self, loading: bool = False) -> str:
        ts = self.capacity.fetched_at if self.capacity else "—"
        indicator = " · refreshing…" if loading else ""
        return (
            f" Cluster · {self.profile_name} │ Updated: {ts}{indicator}"
        )

    def _set_header(self, *, loading: bool) -> None:
        try:
            header = self.query_one("#dashboard-header", DashboardHeader)
            header.update(self._header_text(loading=loading))
        except Exception:
            pass

    def _render_all(self) -> None:
        self._render_capacity()
        self._render_partitions()
        self._render_nodes()
        self._set_header(loading=False)

    def _render_capacity(self) -> None:
        body = self.query_one("#capacity-block", DashboardBody)
        if self.capacity is None:
            body.update(Text("Loading cluster data…", style="dim italic"))
            return

        cap = self.capacity
        text = Text()
        text.append("Capacity\n", style="bold underline")
        text.append("  CPUs:  ", style="dim")
        text.append_text(render_bar(cap.cpu_percentage))
        text.append(f"  {cap.cpus_used} / {cap.cpus_total}\n")
        text.append("  GPUs:  ", style="dim")
        text.append_text(render_bar(cap.gpu_percentage))
        text.append(f"  {cap.gpus_used} / {cap.gpus_total}\n")
        text.append("  Mem:   ", style="dim")
        text.append_text(render_bar(cap.mem_percentage))
        text.append(
            f"  {_format_mem_mb(cap.mem_used_mb)} / {_format_mem_mb(cap.mem_total_mb)}\n"
        )
        text.append("  Nodes: ", style="dim")
        text.append(f"{cap.nodes_up} up", style="green")
        text.append(" · ")
        text.append(f"{cap.nodes_drain} drain", style="magenta" if cap.nodes_drain else "dim")
        text.append(" · ")
        text.append(f"{cap.nodes_down} down", style="red" if cap.nodes_down else "dim")
        body.update(text)

    def _render_partitions(self) -> None:
        table = self.query_one("#partition-table", DataTable)
        table.clear()
        for p in self.partitions:
            cpus_free = max(p.cpus_total - p.cpus_alloc, 0)
            gpus_used = p.gpus_used
            gpus_total = p.gpus_total
            avail_text = Text("up", style="green") if p.available else Text("down", style="red")
            table.add_row(
                p.name,
                f"{p.nodes_idle}/{p.nodes_mixed}/{p.nodes_alloc}/{p.nodes_down}",
                f"{cpus_free}/{p.cpus_total}",
                f"{gpus_used}/{gpus_total}" if gpus_total else "-",
                _format_mem_mb(p.mem_total_mb),
                avail_text,
                key=p.name,
            )

    def _render_nodes(self) -> None:
        table = self.query_one("#node-table", DataTable)
        table.clear()
        for n in self.nodes:
            reason = n.reason if n.reason else ""
            gpu_cell = (
                f"{n.gpus_used}/{n.gpus_total}" if n.gpus_total else "-"
            )
            table.add_row(
                n.name,
                n.partition,
                _state_text(n.state),
                f"{n.cpus_alloc}/{n.cpus_total}",
                f"{_format_mem_mb(n.mem_free_mb)}/{_format_mem_mb(n.mem_total_mb)}",
                gpu_cell,
                reason,
                key=n.name,
            )
