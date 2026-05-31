"""Full-page job detail: live resource stats, progress bars, and actions.

Pulls ``scontrol``/``sstat``/``nvidia-smi`` data via
``scontrol_parser.fetch_job_details`` on a worker thread, plus the favourite /
note state from the history DB (when enabled). Offers scancel, favourite/note,
and navigation to the log and batch-script pages.
"""

import html
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from slurmhub.gui.controller import AppController
from slurmhub.gui.dialogs.confirm import confirm
from slurmhub.gui.widgets import CapacityBar
from slurmhub.gui.workers import run_async
from slurmhub.slurm.scontrol import fetch_job_details
from slurmhub.slurm.squeue import SlurmJob

_TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"}


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

        self.info = QLabel("Loading job details…")
        self.info.setObjectName("HeaderStatus")
        self.info.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.info.setWordWrap(True)
        self.info.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        body_layout.addWidget(self.info)
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
            pk = fav = note = None
            if db is not None and repo is not None:
                with db.session() as s:
                    pk = repo.get_job_pk(s, profile, job.job_id, job.submit_time or "")
                    if pk is not None:
                        fav, note = repo.favourite_state(s, pk)
            return details, pk, bool(fav), note or ""

        run_async(_fetch, self._on_loaded, self._on_error)

    def _on_loaded(self, result) -> None:
        details, pk, favourite, note = result
        self._pk = pk
        self._favourite = favourite
        self._note = note
        self._update_favourite_button()
        self._render_details(details)

    def _on_error(self, exc: Exception) -> None:
        self.info.setText(f"Failed to load job details: {html.escape(str(exc))}")

    def _render_details(self, d) -> None:
        self.time_bar.set_value(
            d.time_percentage, f"{d.run_time or '—'} / {d.time_limit or '—'}"
        )
        self.mem_bar.set_value(
            d.mem_percentage, f"{d.mem_used or '—'} / {d.mem_requested or '—'}"
        )

        # Rebuild per-GPU bars.
        while self.gpu_layout.count():
            item = self.gpu_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for gpu in d.gpus:
            bar = CapacityBar(f"GPU {gpu.index} · {gpu.name}")
            bar.set_value(gpu.utilization, f"{gpu.mem_used_mb}/{gpu.mem_total_mb} MB")
            self.gpu_layout.addWidget(bar)

        def esc(value) -> str:
            return html.escape(str(value)) if value not in (None, "") else "—"

        lines = [
            f"Partition: {esc(d.partition)} &nbsp;|&nbsp; Nodes: {esc(d.node_list)} "
            f"&nbsp;|&nbsp; CPUs: {esc(d.num_cpus)} &nbsp;|&nbsp; GPUs: {esc(d.num_gpus)}",
            f"Submitted: {esc(d.submit_time)} &nbsp;|&nbsp; Started: {esc(d.start_time)} "
            f"&nbsp;|&nbsp; Ended: {esc(d.end_time)}",
            f"Command: <code>{esc(d.command)}</code>",
            f"stdout: {esc(d.stdout_path)}",
            f"stderr: {esc(d.stderr_path)}",
        ]
        if self._note:
            lines.append(f"Note: {esc(self._note)}")
        self.info.setText("<br>".join(lines))

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

        self.navigator.open_subview(
            LogViewer(self.controller, self.profile_name, self.job, self.navigator)
        )

    def _open_batch(self) -> None:
        from slurmhub.gui.views.batch_script_view import BatchScriptView

        self.navigator.open_subview(
            BatchScriptView(self.controller, self.profile_name, self.job, self.navigator)
        )
