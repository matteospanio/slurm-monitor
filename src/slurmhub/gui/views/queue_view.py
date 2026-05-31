"""The Queue / My Jobs screen.

A sortable table of the active profile's merged active+historical jobs, with a
state filter, a name/ID search, a manual refresh, a cluster summary strip, and a
collapsible detail panel below. Cancelling a job (scancel) runs through the
controller behind a confirmation. All data comes from the active
:class:`ProfileSession`; the view never touches SSH/DB itself.
"""

import html
from typing import Optional

from PySide6.QtCore import QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from slurmhub.gui.controller import AppController, get_filtered_jobs
from slurmhub.gui.dialogs.confirm import confirm
from slurmhub.gui.icons import button_icon
from slurmhub.gui.models.delegates import StateBadgeDelegate
from slurmhub.gui.models.jobs_model import JOB_ROLE, SORT_ROLE, JobsModel
from slurmhub.gui.theme import token
from slurmhub.gui.widgets import StatStrip
from slurmhub.slurm.squeue import SlurmJob

# (label, state value used by get_filtered_jobs).
_STATE_FILTERS = [
    ("All states", "ALL"),
    ("Running", "RUNNING"),
    ("Pending", "PENDING"),
    ("Completed", "COMPLETED"),
    ("Failed", "FAILED"),
]

_TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"}


class QueueView(QWidget):
    jobActivated = Signal(object)  # emits the selected SlurmJob (open detail)
    logRequested = Signal(object)  # emits the selected SlurmJob (open log)

    def __init__(
        self, controller: AppController, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self._build_ui()
        self._connect_signals()
        self.reload()

    # ── construction ─────────────────────────────────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addLayout(self._build_toolbar())

        self.stats = StatStrip()
        layout.addWidget(self.stats)

        self.summary = QLabel("")
        self.summary.setObjectName("HeaderStatus")
        layout.addWidget(self.summary)

        self.mode_hint = QLabel("")
        self.mode_hint.setObjectName("HeaderStatus")
        self.mode_hint.setWordWrap(True)
        layout.addWidget(self.mode_hint)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._build_table())
        splitter.addWidget(self._build_detail_panel())
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setCollapsible(1, True)
        layout.addWidget(splitter, 1)

    def _build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["My jobs", "Entire cluster queue"])
        self.scope_combo.setMinimumWidth(170)
        self.scope_combo.currentIndexChanged.connect(self._on_scope_changed)
        bar.addWidget(self.scope_combo)

        self.state_filter = QComboBox()
        for label, _value in _STATE_FILTERS:
            self.state_filter.addItem(label)
        self.state_filter.setMinimumWidth(128)
        self.state_filter.currentIndexChanged.connect(self._on_state_filter_changed)
        bar.addWidget(self.state_filter)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter by job name or ID…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_search_changed)
        bar.addWidget(self.search, 1)

        self.details_button = QPushButton(button_icon("fa5s.eye"), "Details")
        self.details_button.setEnabled(False)
        self.details_button.setToolTip("Open the selected job's full detail screen")
        self.details_button.clicked.connect(self._emit_activated)
        bar.addWidget(self.details_button)

        self.cancel_button = QPushButton(
            button_icon("fa5s.ban", color=token("failed").name()), "Cancel job"
        )
        self.cancel_button.setObjectName("Danger")
        self.cancel_button.setEnabled(False)
        self.cancel_button.setToolTip("Select a non-terminal job to cancel it")
        self.cancel_button.clicked.connect(self._cancel_selected)
        bar.addWidget(self.cancel_button)

        self.refresh_button = QPushButton(button_icon("fa5s.sync-alt"), "Refresh")
        self.refresh_button.setToolTip("Fetch live data for the active profile now")
        self.refresh_button.clicked.connect(self.controller.force_refresh_active)
        bar.addWidget(self.refresh_button)

        return bar

    def _build_table(self) -> QTableView:
        self.model = JobsModel()
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setItemDelegateForColumn(2, StateBadgeDelegate(self.table))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setMinimumSectionSize(70)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch  # Name column expands
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            6, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        self.table.doubleClicked.connect(self._emit_activated)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        delete_sc = QShortcut(QKeySequence(Qt.Key.Key_Delete), self.table)
        delete_sc.activated.connect(self._cancel_selected)
        return self.table

    def _build_detail_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("DetailPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(10, 8, 10, 8)
        self.detail = QLabel("Select a job to see details.")
        self.detail.setObjectName("HeaderStatus")
        self.detail.setWordWrap(True)
        self.detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.detail.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        panel_layout.addWidget(self.detail)
        return panel

    # ── signals ──────────────────────────────────────────────────────
    def _connect_signals(self) -> None:
        self.controller.jobsUpdated.connect(self._on_jobs_updated)
        self.controller.connectionChanged.connect(self._on_connection_changed)
        self.controller.activeProfileChanged.connect(self._on_active_profile_changed)
        self.table.selectionModel().currentRowChanged.connect(
            self._on_selection_changed
        )

    def _on_jobs_updated(self, name: str) -> None:
        if name == self.controller.active_profile:
            self.reload()

    def _on_active_profile_changed(self, _name: str) -> None:
        session = self.controller.session()
        if session is not None:
            # Reflect the new profile's remembered filter/search in the toolbar.
            self.search.blockSignals(True)
            self.search.setText(session.name_filter)
            self.search.blockSignals(False)
            self._select_state_combo(session.state_filter)
            self._set_scope_combo(session.queue_scope)
        self.reload()

    def _on_scope_changed(self, index: int) -> None:
        session = self.controller.session()
        if session is None:
            return
        new_scope = "all" if index == 1 else "me"
        if session.queue_scope == new_scope:
            return
        session.queue_scope = new_scope
        # Force a fresh fetch path when switching scope.
        session._sacct_last_fetch = 0.0
        self.controller.force_refresh_active()

    def _on_connection_changed(self, name: str) -> None:
        if name != self.controller.active_profile:
            return
        session = self.controller.session()
        if session is not None:
            self._update_summary(session)
            self._update_detail(self.selected_job())

    def _on_state_filter_changed(self, index: int) -> None:
        session = self.controller.session()
        if session is None:
            return
        session.state_filter = _STATE_FILTERS[index][1]
        self.reload()

    def _on_search_changed(self, text: str) -> None:
        session = self.controller.session()
        if session is None:
            return
        session.name_filter = text.strip()
        self.reload()

    def _on_selection_changed(self, *_args) -> None:
        self._update_detail(self.selected_job())

    # ── data ─────────────────────────────────────────────────────────
    def reload(self) -> None:
        session = self.controller.session()
        if session is None:
            self.model.set_jobs([])
            self.summary.setText("No profile selected.")
            return
        self.model.set_jobs(get_filtered_jobs(session))
        self._update_summary(session)
        self._update_detail(self.selected_job())

    def selected_job(self) -> Optional[SlurmJob]:
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        return self.proxy.data(index, JOB_ROLE)

    def _update_summary(self, session) -> None:
        self._update_tiles(session)
        scope = "Cluster queue" if session.queue_scope == "all" else "My jobs"
        parts: list[str] = [f"Scope: {scope}"]
        stats = session.queue_stats
        if stats is not None:
            parts.append(
                f"Queue: {stats.total_running} running / "
                f"{stats.total_pending} pending / {stats.total_other} other"
            )
        if session.last_updated:
            parts.append(f"Updated {session.last_updated}")
        self.summary.setText(
            "   •   ".join(parts) if parts else "Waiting for first refresh..."
        )

        if session.error_message:
            self._set_status_label(
                self.mode_hint,
                f"Unable to fetch live data: {session.error_message}",
                "error",
            )
            return
        if session.is_cached:
            self._set_status_label(
                self.mode_hint,
                "Showing cached data while a live refresh runs. "
                "Job-changing actions are temporarily disabled.",
                "loading",
            )
            return
        if session.action_in_progress and session.action_verb and session.action_job_id:
            self._set_status_label(
                self.mode_hint,
                f"Applying '{session.action_verb}' to job "
                f"{session.action_job_id}...",
                "loading",
            )
            return
        if session.is_loading:
            self._set_status_label(
                self.mode_hint,
                "Refreshing live queue and cluster metrics...",
                "loading",
            )
            return
        if session.queue_scope == "all":
            self._set_status_label(
                self.mode_hint,
                "Cluster scope enabled: showing all jobs in the queue. "
                "State-changing actions are disabled in this mode.",
                "",
            )
            return
        self._set_status_label(self.mode_hint, "", "")

    def _update_detail(self, job: Optional[SlurmJob]) -> None:
        session = self.controller.session()
        cached = session is not None and session.is_cached
        action_busy = session is not None and session.action_in_progress
        self.details_button.setEnabled(job is not None)
        cancel_reason = self._cancel_disabled_reason(job, session)
        self.cancel_button.setEnabled(cancel_reason is None)
        self.cancel_button.setToolTip(cancel_reason or "Cancel the selected job")
        if job is None:
            self.detail.setText("Select a job to see details.")
            return

        def esc(value) -> str:
            return html.escape(str(value)) if value not in (None, "") else "—"

        lines = [
            f"<b>{esc(job.job_id)}</b> &nbsp; {esc(job.name)}",
            f"State: {esc(job.state)} &nbsp;|&nbsp; Time: {esc(job.time)} "
            f"&nbsp;|&nbsp; CPUs: {esc(job.num_cpus)} "
            f"&nbsp;|&nbsp; GPU: {esc(job.gpu_display)}",
            f"Work dir: {esc(job.work_dir)}",
        ]
        if job.state == "PENDING":
            lines.append(
                f"Pending reason: {esc(job.pending_reason)} "
                f"&nbsp;|&nbsp; Queue rank: {esc(job.queue_rank)} "
                f"&nbsp;|&nbsp; Priority: {esc(job.priority)}"
            )
        if cached:
            lines.append(
                "<i>Read-only mode: the view is showing cached data until the "
                "next live refresh completes.</i>"
            )
        elif session is not None and session.queue_scope == "all":
            lines.append(
                "<i>Cluster queue scope is active; state-changing actions are "
                "disabled to avoid mutating jobs outside your own queue.</i>"
            )
        elif action_busy and session is not None:
            lines.append(
                "<i>One job action is currently running. Additional state "
                "changes are paused until it completes.</i>"
            )
        elif job.state in _TERMINAL_STATES:
            lines.append(
                "<i>This job is in a terminal state; state-changing actions "
                "are disabled.</i>"
            )
        self.detail.setText("<br>".join(lines))

    # ── actions ──────────────────────────────────────────────────────
    def _cancel_selected(self) -> None:
        job = self.selected_job()
        reason = self._cancel_disabled_reason(job, self.controller.session())
        if reason is not None:
            return
        if confirm(
            self,
            "Cancel job",
            f"Cancel job {job.job_id} ({job.name})?",
            dangerous=True,
            confirm_label="scancel",
        ):
            profile = self.controller.active_profile
            if profile:
                self.controller.cancel_job(profile, job.job_id)

    def _emit_activated(self, *_args) -> None:
        job = self.selected_job()
        if job is not None:
            self.jobActivated.emit(job)

    def _show_context_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        if index.isValid():
            self.table.setCurrentIndex(index)
        job = self.selected_job()
        if job is None:
            return
        session = self.controller.session()
        cached = session is not None and session.is_cached
        action_busy = session is not None and session.action_in_progress
        cluster_scope = session is not None and session.queue_scope == "all"
        # While showing cached data, only read-only actions are offered.
        active = (
            job.state not in _TERMINAL_STATES
            and not cached
            and not action_busy
            and not cluster_scope
        )

        menu = QMenu(self)
        menu.addAction("Details", self._emit_activated)
        menu.addAction("View log", lambda: self.logRequested.emit(self.selected_job()))
        if not active:
            reason = self._cancel_disabled_reason(job, session)
            if reason is not None:
                disabled = menu.addAction(reason)
                disabled.setEnabled(False)
        menu.addSeparator()
        if active:
            menu.addAction("Requeue", self._requeue_selected)
            if job.state == "PENDING":
                menu.addAction("Release", self._release_selected)
            else:
                menu.addAction("Hold", self._hold_selected)
        menu.addSeparator()
        menu.addAction("Copy job ID", self._copy_job_id)
        menu.addAction("Copy log path", self._copy_log_path)
        if active:
            menu.addSeparator()
            menu.addAction("Cancel (scancel)", self._cancel_selected)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _requeue_selected(self) -> None:
        job = self.selected_job()
        profile = self.controller.active_profile
        if job is None or profile is None:
            return
        if confirm(
            self,
            "Requeue job",
            f"Requeue job {job.job_id} ({job.name})? It will be cancelled and "
            "re-run from the start.",
            dangerous=True,
            confirm_label="Requeue",
        ):
            self.controller.requeue_job(profile, job.job_id)

    def _hold_selected(self) -> None:
        job = self.selected_job()
        profile = self.controller.active_profile
        if job is not None and profile is not None:
            self.controller.hold_job(profile, job.job_id)

    def _release_selected(self) -> None:
        job = self.selected_job()
        profile = self.controller.active_profile
        if job is not None and profile is not None:
            self.controller.release_job(profile, job.job_id)

    def _copy_job_id(self) -> None:
        job = self.selected_job()
        if job is not None:
            QApplication.clipboard().setText(job.job_id)

    def _copy_log_path(self) -> None:
        job = self.selected_job()
        session = self.controller.session()
        if job is not None and session is not None:
            path = session.path_resolver.resolve_path(job.job_id, job.work_dir)
            QApplication.clipboard().setText(path)

    def _update_tiles(self, session) -> None:
        jobs = session.jobs
        running = sum(1 for j in jobs if j.state == "RUNNING")
        pending = sum(1 for j in jobs if j.state == "PENDING")
        label = "In queue" if session.queue_scope == "all" else "My jobs"
        self.stats.set_tile("jobs", label, str(len(jobs)))
        self.stats.set_tile(
            "running", "Running", str(running), token("running") if running else None
        )
        self.stats.set_tile(
            "pending", "Pending", str(pending), token("pending") if pending else None
        )
        cap = session.cluster_capacity
        self.stats.set_tile(
            "cpu", "Cluster CPU", f"{cap.cpu_percentage:.0f}%" if cap else "—"
        )
        if cap is not None and cap.gpus_total:
            self.stats.set_tile("gpu", "Cluster GPU", f"{cap.gpu_percentage:.0f}%")

    # ── helpers ──────────────────────────────────────────────────────
    def _select_state_combo(self, state_value: str) -> None:
        for i, (_label, value) in enumerate(_STATE_FILTERS):
            if value == state_value:
                self.state_filter.blockSignals(True)
                self.state_filter.setCurrentIndex(i)
                self.state_filter.blockSignals(False)
                return

    def _set_scope_combo(self, scope: str) -> None:
        idx = 1 if scope == "all" else 0
        self.scope_combo.blockSignals(True)
        self.scope_combo.setCurrentIndex(idx)
        self.scope_combo.blockSignals(False)

    def _cancel_disabled_reason(
        self, job: Optional[SlurmJob], session
    ) -> Optional[str]:
        if job is None:
            return "Select a job first."
        if session is not None and session.queue_scope == "all":
            return "Actions are disabled in whole-cluster scope."
        if session is not None and session.is_cached:
            return "Actions are disabled while cached data is shown."
        if session is not None and session.action_in_progress:
            return "Wait for the current job action to finish."
        if job.state in _TERMINAL_STATES:
            return "This job is already in a terminal state."
        return None

    @staticmethod
    def _set_status_label(label: QLabel, text: str, state: str) -> None:
        label.setText(text)
        label.setProperty("state", state)
        label.style().unpolish(label)
        label.style().polish(label)
