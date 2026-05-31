"""The History & analytics screen.

A filterable table of persisted runs (date range, profile, state, favourites,
search) plus a usage tab with resource-hour totals and a per-profile QtCharts
bar chart. Reads run on worker threads via ``Repository.query_runs`` /
``aggregate_usage``; favourites/notes mutate through ``set_favourite`` /
``set_note``. All DB sessions are opened inside the worker (never shared across
threads).
"""

from datetime import timedelta
from typing import Optional

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QValueAxis,
)
from PySide6.QtCore import QMargins, Qt, QThreadPool
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from slurmhub.db.models import utcnow
from slurmhub.gui.controller import AppController
from slurmhub.gui.icons import button_icon
from slurmhub.gui.models.delegates import StateBadgeDelegate
from slurmhub.gui.models.jobs_model import format_mem_mb
from slurmhub.gui.theme import token
from slurmhub.gui.models.simple_table import ROW_ROLE, Column, SimpleTableModel
from slurmhub.gui.workers import FetchTask
from slurmhub.slurm.squeue import SlurmJob

# (key, label, days) — mirrors the TUI history screen.
_DATE_RANGES = [
    ("all", "All time", None),
    ("24h", "Last 24h", 1),
    ("7d", "Last 7 days", 7),
    ("30d", "Last 30 days", 30),
]
# (label, states or None). FAILED groups the terminal-error states.
_STATE_FILTERS = [
    ("All states", None),
    ("Running", ["RUNNING"]),
    ("Pending", ["PENDING"]),
    ("Completed", ["COMPLETED"]),
    ("Failed", ["FAILED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL"]),
]


def _fmt_elapsed(secs: Optional[int]) -> str:
    if not secs:
        return "" if secs is None else "0:00"
    hours, rem = divmod(secs, 3600)
    minutes, seconds = divmod(rem, 60)
    return (
        f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"
    )


def _fmt_dt(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value is not None else ""


def _fmt_gpu(run) -> str:
    if not run.gpu_count:
        return ""
    return (
        f"{run.gpu_count}x {run.gpu_type}" if run.gpu_type else f"{run.gpu_count}x gpu"
    )


_RUN_COLUMNS = [
    Column("★", lambda r: "★" if r.favourite else ""),
    Column("Job ID", lambda r: r.job_id),
    Column("Name", lambda r: r.name),
    Column("State", lambda r: r.state),
    Column("Profile", lambda r: r.profile_name),
    Column("CPUs", lambda r: r.num_cpus or "", numeric=True),
    Column("GPU", _fmt_gpu),
    Column("Memory", lambda r: format_mem_mb(r.mem_requested_mb), numeric=True),
    Column("Elapsed", lambda r: _fmt_elapsed(r.elapsed_seconds), numeric=True),
    Column("Last seen", lambda r: _fmt_dt(r.last_seen)),
    Column("Note", lambda r: r.note or ""),
]


class HistoryView(QWidget):
    def __init__(
        self,
        controller: AppController,
        navigator: Optional[QWidget] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.navigator = navigator
        self._build_ui()
        self.reload()

    # ── construction ─────────────────────────────────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addLayout(self._build_filters())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_runs_tab(), "Runs")
        self.tabs.addTab(self._build_usage_tab(), "Usage")
        layout.addWidget(self.tabs, 1)

        self.status = QLabel("")
        self.status.setObjectName("HeaderStatus")
        layout.addWidget(self.status)

    def _build_filters(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self.range_combo = QComboBox()
        for _key, label, _days in _DATE_RANGES:
            self.range_combo.addItem(label)
        self.range_combo.currentIndexChanged.connect(self.reload)
        bar.addWidget(self.range_combo)

        self.state_combo = QComboBox()
        for label, _states in _STATE_FILTERS:
            self.state_combo.addItem(label)
        self.state_combo.currentIndexChanged.connect(self.reload)
        bar.addWidget(self.state_combo)

        self.profile_combo = QComboBox()
        self.profile_combo.addItem("All profiles")
        self.profile_combo.addItems(self.controller.profile_names)
        self.profile_combo.currentIndexChanged.connect(self.reload)
        bar.addWidget(self.profile_combo)

        self.favourites_only = QCheckBox("★ only")
        self.favourites_only.toggled.connect(self.reload)
        bar.addWidget(self.favourites_only)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search name or ID…")
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self.reload)
        bar.addWidget(self.search, 1)

        refresh = QPushButton(button_icon("fa5s.sync-alt"), "Refresh")
        refresh.clicked.connect(self.reload)
        bar.addWidget(refresh)
        return bar

    def _build_runs_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 0)

        self.model = SimpleTableModel(_RUN_COLUMNS)
        self.table = QTableView()
        self.table.setModel(self.model)
        # Column 3 is "State" — render it as the same colour-coded pill as Queue.
        self.table.setItemDelegateForColumn(3, StateBadgeDelegate(self.table))
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._open_details)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.details_button = QPushButton(button_icon("fa5s.info-circle"), "Details")
        self.details_button.clicked.connect(self._open_details)
        self.fav_button = QPushButton(button_icon("fa5s.star"), "Toggle favourite")
        self.fav_button.clicked.connect(self._toggle_favourite)
        self.note_button = QPushButton(button_icon("fa5s.pen"), "Edit note…")
        self.note_button.clicked.connect(self._edit_note)
        actions.addWidget(self.details_button)
        actions.addWidget(self.fav_button)
        actions.addWidget(self.note_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        return page

    def _build_usage_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(12)

        summary_card = QFrame()
        summary_card.setObjectName("JobCard")
        sc_layout = QVBoxLayout(summary_card)
        sc_layout.setContentsMargins(16, 12, 16, 12)
        sc_layout.setSpacing(4)
        sc_title = QLabel("Totals")
        sc_title.setObjectName("JobCardTitle")
        sc_layout.addWidget(sc_title)
        self.usage_summary = QLabel("")
        self.usage_summary.setObjectName("HeaderStatus")
        self.usage_summary.setWordWrap(True)
        sc_layout.addWidget(self.usage_summary)
        layout.addWidget(summary_card)

        chart_card = QFrame()
        chart_card.setObjectName("JobCard")
        cc_layout = QVBoxLayout(chart_card)
        cc_layout.setContentsMargins(16, 12, 16, 12)
        cc_layout.setSpacing(8)
        cc_title = QLabel("Resource hours by profile")
        cc_title.setObjectName("JobCardTitle")
        cc_layout.addWidget(cc_title)

        self.chart = QChart()
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.chart.setBackgroundVisible(False)
        self.chart.setMargins(QMargins(0, 0, 0, 0))
        self.chart.legend().setVisible(True)
        self.chart.legend().setLabelColor(token("text_muted"))
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view.setStyleSheet("background: transparent; border: none;")
        cc_layout.addWidget(self.chart_view, 1)
        layout.addWidget(chart_card, 1)
        return page

    # ── filter args ──────────────────────────────────────────────────
    def _query_kwargs(self) -> dict:
        days = _DATE_RANGES[self.range_combo.currentIndex()][2]
        since = utcnow() - timedelta(days=days) if days else None
        states = _STATE_FILTERS[self.state_combo.currentIndex()][1]
        profile = (
            None
            if self.profile_combo.currentIndex() == 0
            else self.profile_combo.currentText()
        )
        return {
            "profile": profile,
            "states": states,
            "since": since,
            "favourites_only": self.favourites_only.isChecked(),
            "search": self.search.text().strip() or None,
        }

    # ── data ─────────────────────────────────────────────────────────
    def reload(self) -> None:
        if self.controller.database is None or self.controller.repository is None:
            self.status.setText(
                "Job history is disabled — enable it in Settings → Database."
            )
            self.model.set_rows([])
            return

        db = self.controller.database
        repo = self.controller.repository
        kwargs = self._query_kwargs()

        def _query():
            with db.session() as session:
                runs = repo.query_runs(session, **kwargs)
                totals = repo.aggregate_usage(
                    session,
                    profile=kwargs["profile"],
                    since=kwargs["since"],
                )
            return runs, totals

        task = FetchTask(_query)
        task.signals.finished.connect(self._on_loaded)
        task.signals.failed.connect(self._on_error)
        QThreadPool.globalInstance().start(task)

    def _on_loaded(self, result) -> None:
        runs, totals = result
        self.model.set_rows(runs)
        self.status.setText(f"{len(runs)} run(s)")
        self._update_usage(totals)

    def _on_error(self, exc: Exception) -> None:
        self.status.setText(f"History query failed: {exc}")

    def _update_usage(self, totals) -> None:
        util = (
            f"{totals.avg_gpu_util:.0f}%" if totals.avg_gpu_util is not None else "n/a"
        )
        self.usage_summary.setText(
            f"<b>{totals.job_count}</b> runs &nbsp;•&nbsp; "
            f"GPU-hours: <b>{totals.gpu_hours:g}</b> &nbsp;•&nbsp; "
            f"CPU-hours: <b>{totals.cpu_hours:g}</b> &nbsp;•&nbsp; "
            f"Memory GB·h: <b>{totals.mem_gb_hours:g}</b> &nbsp;•&nbsp; "
            f"avg GPU util: <b>{util}</b>"
        )

        # Per-profile GPU/CPU hours bar chart (overall row when single profile).
        rows = totals.per_profile or [totals]
        categories = [r.profile_name or "all" for r in rows]
        gpu_set = QBarSet("GPU-hours")
        gpu_set.setColor(token("accent"))
        gpu_set.setBorderColor(token("accent"))
        cpu_set = QBarSet("CPU-hours")
        cpu_set.setColor(token("running"))
        cpu_set.setBorderColor(token("running"))
        for r in rows:
            gpu_set.append(r.gpu_hours)
            cpu_set.append(r.cpu_hours)

        series = QBarSeries()
        series.append(gpu_set)
        series.append(cpu_set)

        self.chart.removeAllSeries()
        for axis in list(self.chart.axes()):
            self.chart.removeAxis(axis)
        self.chart.addSeries(series)

        muted = token("text_muted")
        border = token("border")
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsColor(muted)
        axis_x.setGridLineColor(border)
        axis_x.setLinePen(border)
        self.chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        max_val = max([r.gpu_hours for r in rows] + [r.cpu_hours for r in rows] + [1.0])
        axis_y.setRange(0, max_val * 1.1)
        axis_y.setLabelsColor(muted)
        axis_y.setGridLineColor(border)
        axis_y.setLinePen(border)
        self.chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)
        self.chart.legend().setLabelColor(muted)

    # ── favourites / notes ───────────────────────────────────────────
    def selected_run(self):
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        return self.model.data(index, ROW_ROLE)

    def _mutate(self, fn) -> None:
        db = self.controller.database
        if db is None:
            return

        def _run():
            with db.session() as session:
                fn(session)
            return True

        task = FetchTask(_run)
        # Bound-method slot (not a lambda) so the result is delivered on the
        # main thread — see the note in AppController.refresh_profile.
        task.signals.finished.connect(self._on_mutated)
        task.signals.failed.connect(self._on_error)
        QThreadPool.globalInstance().start(task)

    def _on_mutated(self, _ok) -> None:
        self.reload()

    def _toggle_favourite(self) -> None:
        run = self.selected_run()
        if run is None:
            return
        repo = self.controller.repository
        new_state = not run.favourite
        self._mutate(lambda s: repo.set_favourite(s, run.pk, new_state))

    def _open_details(self, *_args) -> None:
        run = self.selected_run()
        if run is None:
            return
        if self.navigator is None or not hasattr(self.navigator, "open_subview"):
            return
        if self.controller.session(run.profile_name) is None:
            self.status.setText(
                f"Cannot open details: profile '{run.profile_name}' no longer exists."
            )
            return

        from slurmhub.gui.views.job_detail_view import JobDetailView

        gres = None
        if run.gpu_count:
            gres = (
                f"gpu:{run.gpu_type}:{run.gpu_count}"
                if run.gpu_type
                else f"gpu:{run.gpu_count}"
            )

        job = SlurmJob(
            job_id=run.job_id,
            name=run.name,
            state=run.state,
            time=_fmt_elapsed(run.elapsed_seconds) or "0:00",
            work_dir=run.work_dir,
            gres=gres,
            submit_time=run.submit_time,
            num_cpus=run.num_cpus,
            mem_requested_mb=run.mem_requested_mb,
        )
        self.navigator.open_subview(
            JobDetailView(self.controller, run.profile_name, job, self.navigator)
        )

    def _edit_note(self) -> None:
        run = self.selected_run()
        if run is None:
            return
        text, ok = QInputDialog.getMultiLineText(
            self, "Edit note", f"Note for job {run.job_id}:", run.note or ""
        )
        if ok:
            repo = self.controller.repository
            self._mutate(lambda s: repo.set_note(s, run.pk, text))
