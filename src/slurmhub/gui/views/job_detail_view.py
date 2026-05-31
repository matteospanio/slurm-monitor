"""Full-page job detail: live resource stats, progress bars, and actions.

Pulls ``scontrol``/``sstat``/``nvidia-smi`` data via
``scontrol_parser.fetch_job_details`` on a worker thread, plus the favourite /
note state from the history DB (when enabled). Offers scancel, favourite/note,
and navigation to the log and batch-script pages.
"""

from typing import Optional

import pyqtgraph as pg

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from slurmhub.gui.controller import AppController
from slurmhub.gui.dialogs.confirm import confirm
from slurmhub.gui.models.jobs_model import format_mem_mb
from slurmhub.gui.theme import token
from slurmhub.gui.widgets import CapacityBar
from slurmhub.gui.workers import run_async
from slurmhub.slurm.scontrol import fetch_job_details
from slurmhub.slurm.squeue import SlurmJob

_TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"}
pg.setConfigOptions(antialias=True)


def _fmt_elapsed(seconds: Optional[int]) -> str:
    if seconds is None:
        return "—"
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes}:{sec:02d}"


def _fmt_when(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value is not None else "—"


def _fmt_pct(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, int):
        return f"{value}%"
    return f"{value:.1f}%"


def _as_text(value) -> str:
    return str(value) if value not in (None, "") else "—"


class JobDetailView(QWidget):
    def __init__(
        self,
        controller: AppController,
        profile_name: str,
        job: SlurmJob,
        navigator,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.profile_name = profile_name
        self.job = job
        self.navigator = navigator
        self._pk: Optional[int] = None
        self._favourite = False
        self._note = ""
        self._stdout_path: Optional[str] = None
        self._stderr_path: Optional[str] = None
        self._usage_points = []
        self._build_ui()
        self._load()

    # ── construction ─────────────────────────────────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        back = QPushButton("← Back")
        back.clicked.connect(self.navigator.go_back)
        top.addWidget(back)
        self.title = QLabel(f"{self.job.job_id} · {self.job.name} · {self.job.state}")
        self.title.setObjectName("HeaderHost")
        top.addWidget(self.title, 1)
        layout.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setSpacing(10)

        self.time_bar = CapacityBar("Time")
        self.mem_bar = CapacityBar("Memory")
        body_layout.addWidget(self.time_bar)
        body_layout.addWidget(self.mem_bar)

        self.gpu_container = QWidget()
        self.gpu_layout = QVBoxLayout(self.gpu_container)
        self.gpu_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(self.gpu_container)

        self.usage_card = QFrame()
        self.usage_card.setObjectName("JobCard")
        usage_layout = QVBoxLayout(self.usage_card)
        usage_layout.setContentsMargins(12, 12, 12, 12)
        usage_layout.setSpacing(6)

        self.usage_title = QLabel("Usage timeline")
        self.usage_title.setObjectName("JobCardTitle")
        usage_layout.addWidget(self.usage_title)

        self.usage_subtitle = QLabel(
            "Interactive native chart: drag to pan, scroll to zoom, hover to inspect samples."
        )
        self.usage_subtitle.setObjectName("JobCardSubtitle")
        self.usage_subtitle.setWordWrap(True)
        usage_layout.addWidget(self.usage_subtitle)

        self.usage_plot = pg.PlotWidget()
        self.usage_plot.setObjectName("JobUsagePlot")
        self.usage_plot.setMinimumHeight(300)
        self.usage_plot.setMenuEnabled(False)
        self.usage_plot.setMouseEnabled(x=True, y=True)
        usage_layout.addWidget(self.usage_plot)

        self.usage_empty = QLabel("No usage snapshots captured yet.")
        self.usage_empty.setObjectName("HeaderStatus")
        self.usage_empty.setVisible(False)
        usage_layout.addWidget(self.usage_empty)

        self.usage_hover = QLabel("Hover the chart to inspect a sample.")
        self.usage_hover.setObjectName("HeaderStatus")
        self.usage_hover.setWordWrap(True)
        usage_layout.addWidget(self.usage_hover)

        body_layout.addWidget(self.usage_card)

        self.usage_plot_item = self.usage_plot.getPlotItem()
        self.usage_plot_item.showGrid(x=True, y=True, alpha=0.2)
        self.usage_plot_item.showAxis("right")
        self._usage_right_vb = pg.ViewBox(enableMenu=False)
        self.usage_plot_item.scene().addItem(self._usage_right_vb)
        self.usage_plot_item.getAxis("right").linkToView(self._usage_right_vb)
        self._usage_right_vb.setXLink(self.usage_plot_item.vb)
        self.usage_plot_item.vb.sigResized.connect(self._sync_usage_plot_views)

        self.usage_legend = self.usage_plot_item.addLegend(offset=(10, 10))
        self.gpu_curve = self.usage_plot_item.plot([], [], name="GPU util %")
        self.cpu_curve = self.usage_plot_item.plot([], [], name="CPU util %")
        self.cpu_alloc_curve = pg.PlotDataItem([], [])
        self._usage_right_vb.addItem(self.cpu_alloc_curve)
        self.usage_legend.addItem(self.cpu_alloc_curve, "CPUs allocated")

        self._usage_mouse_proxy = pg.SignalProxy(
            self.usage_plot.scene().sigMouseMoved,
            rateLimit=30,
            slot=self._on_usage_mouse_moved,
        )

        self._apply_usage_plot_theme()
        self._sync_usage_plot_views()

        self.details_card = QFrame()
        self.details_card.setObjectName("JobCard")
        card_layout = QVBoxLayout(self.details_card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(6)

        details_title = QLabel("Structured job details")
        details_title.setObjectName("JobCardTitle")
        card_layout.addWidget(details_title)

        self.details_status = QLabel("Loading job details…")
        self.details_status.setObjectName("HeaderStatus")
        self.details_status.setWordWrap(True)
        card_layout.addWidget(self.details_status)

        self.details_table = QTableWidget(0, 2)
        self.details_table.setObjectName("JobDetailsTable")
        self.details_table.setHorizontalHeaderLabels(["Field", "Value"])
        self.details_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.details_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.details_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.details_table.setAlternatingRowColors(True)
        self.details_table.verticalHeader().setVisible(False)
        self.details_table.setWordWrap(True)
        header = self.details_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        card_layout.addWidget(self.details_table)

        body_layout.addWidget(self.details_card)
        body_layout.addStretch(1)

        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

        layout.addLayout(self._build_actions())

    def _build_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        session = self.controller.session(self.profile_name)
        cached = session is not None and session.is_cached
        active = self.job.state not in _TERMINAL_STATES and not cached
        self.cancel_button = QPushButton("Cancel job")
        self.cancel_button.setObjectName("Danger")
        self.cancel_button.setEnabled(active)
        self.cancel_button.clicked.connect(self._cancel)
        row.addWidget(self.cancel_button)

        self.requeue_button = QPushButton("Requeue")
        self.requeue_button.setEnabled(active)
        self.requeue_button.clicked.connect(self._requeue)
        row.addWidget(self.requeue_button)

        self.hold_button = QPushButton("Hold")
        self.hold_button.setEnabled(active)
        self.hold_button.clicked.connect(
            lambda: self.controller.hold_job(self.profile_name, self.job.job_id)
        )
        row.addWidget(self.hold_button)

        self.release_button = QPushButton("Release")
        self.release_button.setEnabled(active)
        self.release_button.clicked.connect(
            lambda: self.controller.release_job(self.profile_name, self.job.job_id)
        )
        row.addWidget(self.release_button)

        self.fav_button = QPushButton("☆ Favourite")
        self.fav_button.clicked.connect(self._toggle_favourite)
        self.note_button = QPushButton("Edit note…")
        self.note_button.clicked.connect(self._edit_note)
        has_db = self.controller.database is not None
        self.fav_button.setEnabled(has_db)
        self.note_button.setEnabled(has_db)
        row.addWidget(self.fav_button)
        row.addWidget(self.note_button)

        row.addStretch(1)
        log_btn = QPushButton("View log")
        log_btn.clicked.connect(self._open_log)
        batch_btn = QPushButton("View batch script")
        batch_btn.clicked.connect(self._open_batch)
        row.addWidget(log_btn)
        row.addWidget(batch_btn)
        return row

    # ── load ─────────────────────────────────────────────────────────
    def _load(self) -> None:
        session = self.controller.session(self.profile_name)
        if session is None:
            return
        client = session.ssh_client
        timeout = session.profile.ssh_timeout
        job = self.job
        profile = self.profile_name
        db = self.controller.database
        repo = self.controller.repository

        def _fetch():
            details = fetch_job_details(client, job.job_id, timeout)
            pk = None
            fav = False
            note = ""
            run = None
            metrics = None
            points = []
            if db is not None and repo is not None:
                with db.session() as s:
                    submit = (
                        details.submit_time
                        if details is not None and details.submit_time
                        else (job.submit_time or "")
                    )
                    pk = repo.get_job_pk(s, profile, job.job_id, submit)
                    if pk is not None:
                        run = repo.get_run_by_pk(s, pk)
                    if run is None:
                        run = repo.latest_run_for_job(s, profile, job.job_id)
                        if run is not None:
                            pk = run.pk
                    if pk is not None:
                        fav, note = repo.favourite_state(s, pk)
                        metrics = repo.summarize_run_snapshots(s, pk)
                        points = repo.get_run_snapshots(s, pk)
            return details, run, metrics, points, pk, bool(fav), note

        run_async(_fetch, self._on_loaded, self._on_error)

    def _on_loaded(self, result) -> None:
        details, run, metrics, points, pk, favourite, note = result
        self._pk = pk
        self._favourite = favourite
        self._note = note
        self._update_favourite_button()
        self._render_details(details, run, metrics, points)

    def _on_error(self, exc: Exception) -> None:
        self._set_details_status(f"Failed to load job details: {exc}", state="error")
        self._set_detail_rows([])
        self._render_usage_plot([])

    def _sync_usage_plot_views(self) -> None:
        self._usage_right_vb.setGeometry(self.usage_plot_item.vb.sceneBoundingRect())
        self._usage_right_vb.linkedViewChanged(
            self.usage_plot_item.vb, self._usage_right_vb.XAxis
        )

    def _apply_usage_plot_theme(self) -> None:
        border = token("border")
        text = token("text")
        muted = token("text_muted")

        self.usage_plot.setBackground(token("surface"))
        self.usage_plot_item.setLabel("bottom", "Sample", color=text.name())
        self.usage_plot_item.setLabel("left", "Utilization %", color=text.name())
        self.usage_plot_item.getAxis("right").setLabel(
            "CPUs allocated", color=text.name()
        )

        for axis_name in ("bottom", "left", "right"):
            axis = self.usage_plot_item.getAxis(axis_name)
            axis.setPen(pg.mkPen(border, width=1))
            axis.setTextPen(pg.mkPen(muted, width=1))

        running = token("running")
        pending = token("pending")
        muted_line = token("text_muted")
        self.gpu_curve.setPen(pg.mkPen(running, width=2))
        self.gpu_curve.setSymbol("o")
        self.gpu_curve.setSymbolSize(6)
        self.gpu_curve.setSymbolPen(pg.mkPen(running, width=1))
        self.gpu_curve.setSymbolBrush(running)

        self.cpu_curve.setPen(pg.mkPen(pending, width=2))
        self.cpu_curve.setSymbol("o")
        self.cpu_curve.setSymbolSize(6)
        self.cpu_curve.setSymbolPen(pg.mkPen(pending, width=1))
        self.cpu_curve.setSymbolBrush(pending)

        self.cpu_alloc_curve.setPen(
            pg.mkPen(muted_line, width=2, style=Qt.PenStyle.DashLine)
        )
        self.cpu_alloc_curve.setSymbol("x")
        self.cpu_alloc_curve.setSymbolSize(7)
        self.cpu_alloc_curve.setSymbolPen(pg.mkPen(muted_line, width=1))

        self.usage_legend.setBrush(token("surface2"))
        self.usage_legend.setPen(pg.mkPen(border, width=1))

    def _set_details_status(self, text: str, state: str = "") -> None:
        self.details_status.setText(text)
        self.details_status.setProperty("state", state)
        self.details_status.style().unpolish(self.details_status)
        self.details_status.style().polish(self.details_status)

    def _set_detail_rows(self, rows: list[tuple[str, str]]) -> None:
        self.details_table.setRowCount(len(rows))
        for row_index, (field, value) in enumerate(rows):
            field_item = QTableWidgetItem(field)
            value_item = QTableWidgetItem(value)
            field_item.setFlags(field_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            value_item.setToolTip(value)
            self.details_table.setItem(row_index, 0, field_item)
            self.details_table.setItem(row_index, 1, value_item)
        self.details_table.resizeRowsToContents()

    def _render_details(self, d, run=None, metrics=None, points=None) -> None:
        self._render_usage_plot(points or [])

        self._stdout_path = (
            (d.stdout_path if d is not None else None)
            or (run.stdout_path if run is not None else None)
            or None
        )
        self._stderr_path = (
            (d.stderr_path if d is not None else None)
            or (run.stderr_path if run is not None else None)
            or None
        )

        if d is not None:
            self.time_bar.set_value(
                d.time_percentage, f"{d.run_time or '—'} / {d.time_limit or '—'}"
            )
            self.mem_bar.set_value(
                d.mem_percentage, f"{d.mem_used or '—'} / {d.mem_requested or '—'}"
            )
        elif run is not None:
            self.time_bar.set_value(0.0, _fmt_elapsed(run.elapsed_seconds))
            requested_mb = run.mem_requested_mb
            peak_used_mb = (
                metrics.peak_mem_used_mb
                if metrics is not None and metrics.peak_mem_used_mb is not None
                else None
            )
            if requested_mb and peak_used_mb:
                ratio = min(100.0, peak_used_mb / requested_mb * 100.0)
                self.mem_bar.set_value(
                    ratio,
                    f"peak {format_mem_mb(peak_used_mb)} / "
                    f"allocated {format_mem_mb(requested_mb)}",
                )
            elif requested_mb:
                self.mem_bar.set_value(0.0, f"allocated {format_mem_mb(requested_mb)}")
            else:
                self.mem_bar.set_value(0.0, "—")
        else:
            self.time_bar.set_value(0.0, "—")
            self.mem_bar.set_value(0.0, "—")

        # Rebuild per-GPU bars.
        while self.gpu_layout.count():
            item = self.gpu_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if d is not None:
            for gpu in d.gpus:
                bar = CapacityBar(f"GPU {gpu.index} · {gpu.name}")
                bar.set_value(
                    gpu.utilization, f"{gpu.mem_used_mb}/{gpu.mem_total_mb} MB"
                )
                self.gpu_layout.addWidget(bar)
        elif run is not None and run.gpu_count:
            gpu_label = (
                f"{run.gpu_count}x {run.gpu_type}"
                if run.gpu_type
                else f"{run.gpu_count}x gpu"
            )
            bar = CapacityBar(f"GPU allocation ({gpu_label})")
            peak = (
                metrics.peak_gpu_util
                if metrics is not None and metrics.peak_gpu_util is not None
                else 0
            )
            if metrics is not None and metrics.avg_gpu_util is not None:
                detail = (
                    f"peak {peak}% / avg {metrics.avg_gpu_util:.1f}% "
                    f"across {metrics.snapshot_count} snapshot(s)"
                )
            elif metrics is not None and metrics.snapshot_count:
                detail = f"{metrics.snapshot_count} snapshot(s) captured"
            else:
                detail = "allocation recorded"
            bar.set_value(float(peak), detail)
            self.gpu_layout.addWidget(bar)

        rows: list[tuple[str, str]] = []
        if d is not None:
            self._set_details_status(
                "Live details loaded from the cluster.", state="ok"
            )
            rows = [
                ("Source", "Live cluster query (scontrol/sstat)"),
                ("Partition", _as_text(d.partition)),
                ("Nodes", _as_text(d.node_list)),
                ("CPUs", _as_text(d.num_cpus)),
                ("GPUs", _as_text(d.num_gpus)),
                ("Submitted", _as_text(d.submit_time)),
                ("Started", _as_text(d.start_time)),
                ("Ended", _as_text(d.end_time)),
                ("Command", _as_text(d.command)),
                ("stdout", _as_text(d.stdout_path)),
                ("stderr", _as_text(d.stderr_path)),
            ]
            if metrics is not None and metrics.snapshot_count:
                rows.extend(
                    [
                        (
                            "Snapshots",
                            f"{metrics.snapshot_count} (latest {_fmt_when(metrics.last_captured_at)})",
                        ),
                        (
                            "CPU util (avg / peak)",
                            f"{_fmt_pct(metrics.avg_cpu_util)} / {_fmt_pct(metrics.peak_cpu_util)}",
                        ),
                        (
                            "GPU util (avg / peak)",
                            f"{_fmt_pct(metrics.avg_gpu_util)} / {_fmt_pct(metrics.peak_gpu_util)}",
                        ),
                        (
                            "Memory peak",
                            _as_text(format_mem_mb(metrics.peak_mem_used_mb)),
                        ),
                    ]
                )
        elif run is not None:
            self._set_details_status(
                "Live detail unavailable; showing persisted history from the local database.",
                state="loading",
            )
            rows = [
                ("Source", "Persisted local history"),
                ("Profile", _as_text(run.profile_name)),
                ("State", _as_text(run.state)),
                ("Partition", _as_text(run.partition)),
                ("CPUs", _as_text(run.num_cpus)),
                ("GPUs", _as_text(run.gpu_count)),
                ("Submitted", _as_text(run.submit_time)),
                ("Started", _as_text(run.start_time)),
                ("Ended", _as_text(run.end_time)),
                ("Elapsed", _as_text(_fmt_elapsed(run.elapsed_seconds))),
                ("Memory requested", _as_text(format_mem_mb(run.mem_requested_mb))),
                ("stdout", _as_text(run.stdout_path)),
                ("stderr", _as_text(run.stderr_path)),
            ]
            if metrics is not None and metrics.snapshot_count:
                rows.extend(
                    [
                        (
                            "Snapshots",
                            f"{metrics.snapshot_count} "
                            f"(first {_fmt_when(metrics.first_captured_at)}, "
                            f"last {_fmt_when(metrics.last_captured_at)})",
                        ),
                        (
                            "CPU util (avg / peak)",
                            f"{_fmt_pct(metrics.avg_cpu_util)} / {_fmt_pct(metrics.peak_cpu_util)}",
                        ),
                        (
                            "GPU util (avg / peak)",
                            f"{_fmt_pct(metrics.avg_gpu_util)} / {_fmt_pct(metrics.peak_gpu_util)}",
                        ),
                        (
                            "Memory (latest / peak)",
                            f"{_as_text(format_mem_mb(metrics.latest_mem_used_mb))} / "
                            f"{_as_text(format_mem_mb(metrics.peak_mem_used_mb))}",
                        ),
                    ]
                )
        else:
            self._set_details_status(
                "No live or persisted detail data is available for this job yet.",
                state="error",
            )
            rows = [
                ("Job", _as_text(self.job.job_id)),
                ("Name", _as_text(self.job.name)),
                ("State", _as_text(self.job.state)),
            ]

        if self._note:
            rows.append(("Note", _as_text(self._note)))

        self._set_detail_rows(rows)

    def _render_usage_plot(self, points) -> None:
        self._usage_points = list(points)
        self._apply_usage_plot_theme()

        if not points:
            self.gpu_curve.setData([], [])
            self.cpu_curve.setData([], [])
            self.cpu_alloc_curve.setData([], [])
            self.usage_plot.setVisible(False)
            self.usage_empty.setVisible(True)
            self.usage_title.setText("Usage timeline")
            self.usage_hover.setText("No usage snapshots captured yet.")
            return

        gpu_x: list[int] = []
        gpu_y: list[float] = []
        cpu_x: list[int] = []
        cpu_y: list[float] = []
        alloc_x: list[int] = []
        alloc_y: list[float] = []

        for sample_index, point in enumerate(points, start=1):
            if point.gpu_util_avg is not None:
                gpu_x.append(sample_index)
                gpu_y.append(float(point.gpu_util_avg))
            if point.cpu_util_avg is not None:
                cpu_x.append(sample_index)
                cpu_y.append(float(point.cpu_util_avg))
            if point.num_cpus is not None:
                alloc_x.append(sample_index)
                alloc_y.append(float(point.num_cpus))

        has_gpu = bool(gpu_y)
        has_cpu = bool(cpu_y)
        has_alloc = bool(alloc_y)
        if not has_gpu and not has_cpu and not has_alloc:
            self.gpu_curve.setData([], [])
            self.cpu_curve.setData([], [])
            self.cpu_alloc_curve.setData([], [])
            self.usage_plot.setVisible(False)
            self.usage_empty.setVisible(True)
            self.usage_title.setText(f"Usage timeline ({len(points)} samples)")
            self.usage_hover.setText(
                "Snapshots found, but no utilization values were captured."
            )
            return

        self.gpu_curve.setData(gpu_x, gpu_y)
        self.gpu_curve.setVisible(has_gpu)
        self.cpu_curve.setData(cpu_x, cpu_y)
        self.cpu_curve.setVisible(has_cpu)
        self.cpu_alloc_curve.setData(alloc_x, alloc_y)
        self.cpu_alloc_curve.setVisible(has_alloc)

        self.usage_plot_item.setXRange(0.5, max(1.5, len(points) + 0.5), padding=0)
        util_values = [*gpu_y, *cpu_y]
        util_top = max(util_values) if util_values else 100.0
        self.usage_plot_item.setYRange(0.0, max(100.0, util_top * 1.05), padding=0)

        alloc_top = max(alloc_y) if alloc_y else 1.0
        self._usage_right_vb.setYRange(0.0, max(1.0, alloc_top * 1.1), padding=0)
        self._sync_usage_plot_views()

        self.usage_plot.setVisible(True)
        self.usage_empty.setVisible(False)
        self.usage_title.setText(f"Usage timeline ({len(points)} samples)")
        self.usage_hover.setText("Hover the chart to inspect a sample.")

    def _on_usage_mouse_moved(self, event) -> None:
        if not self._usage_points:
            return
        if not event:
            return

        pos = event[0]
        if not self.usage_plot.sceneBoundingRect().contains(pos):
            return

        mouse_point = self.usage_plot_item.vb.mapSceneToView(pos)
        sample_index = int(round(mouse_point.x())) - 1
        if sample_index < 0 or sample_index >= len(self._usage_points):
            return

        point = self._usage_points[sample_index]
        captured = _fmt_when(point.captured_at)
        self.usage_hover.setText(
            f"Sample {sample_index + 1} @ {captured} · "
            f"CPU {_fmt_pct(point.cpu_util_avg)} · "
            f"GPU {_fmt_pct(point.gpu_util_avg)} · "
            f"CPUs {_as_text(point.num_cpus)} · "
            f"Mem {_as_text(format_mem_mb(point.mem_used_mb))}"
        )

    # ── actions ──────────────────────────────────────────────────────
    def _cancel(self) -> None:
        if confirm(
            self,
            "Cancel job",
            f"Cancel job {self.job.job_id} ({self.job.name})?",
            dangerous=True,
            confirm_label="scancel",
        ):
            self.controller.cancel_job(self.profile_name, self.job.job_id)
            self.navigator.go_back()

    def _requeue(self) -> None:
        if confirm(
            self,
            "Requeue job",
            f"Requeue job {self.job.job_id} ({self.job.name})?",
            dangerous=True,
            confirm_label="Requeue",
        ):
            self.controller.requeue_job(self.profile_name, self.job.job_id)

    def _update_favourite_button(self) -> None:
        self.fav_button.setText("★ Favourited" if self._favourite else "☆ Favourite")

    def _toggle_favourite(self) -> None:
        repo = self.controller.repository
        db = self.controller.database
        if repo is None or db is None:
            return
        job, profile, target = self.job, self.profile_name, not self._favourite

        def _run():
            with db.session() as s:
                pk = repo.upsert_job(s, profile, job)
                repo.set_favourite(s, pk, target)
            return target

        run_async(_run, self._on_favourite_set, self._on_error)

    def _on_favourite_set(self, new_state: bool) -> None:
        self._favourite = new_state
        self._update_favourite_button()

    def _edit_note(self) -> None:
        repo = self.controller.repository
        db = self.controller.database
        if repo is None or db is None:
            return
        text, ok = QInputDialog.getMultiLineText(
            self, "Edit note", f"Note for job {self.job.job_id}:", self._note
        )
        if not ok:
            return
        job, profile = self.job, self.profile_name

        def _run():
            with db.session() as s:
                pk = repo.upsert_job(s, profile, job)
                repo.set_note(s, pk, text)
            return text

        run_async(_run, self._on_note_set, self._on_error)

    def _on_note_set(self, note: str) -> None:
        self._note = note

    def _open_log(self) -> None:
        from slurmhub.gui.views.log_viewer import LogViewer

        path = self._stdout_path or self._stderr_path
        self.navigator.open_subview(
            LogViewer(
                self.controller,
                self.profile_name,
                self.job,
                self.navigator,
                log_path=path,
            )
        )

    def _open_batch(self) -> None:
        from slurmhub.gui.views.batch_script_view import BatchScriptView

        self.navigator.open_subview(
            BatchScriptView(
                self.controller, self.profile_name, self.job, self.navigator
            )
        )
