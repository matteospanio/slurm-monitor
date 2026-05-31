"""Read-only viewer for a job's submitted sbatch script.

Fetches ``scontrol write batch_script <id> -`` once on a worker thread (a small,
finite payload — ``execute`` rather than streaming, which also works in --demo).
"""

import shlex
from typing import Optional

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from slurmhub.qt.controller import AppController
from slurmhub.qt.workers import run_async
from slurmhub.squeue_parser import SlurmJob


class BatchScriptView(QWidget):
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
        self.job = job
        self.navigator = navigator
        session = controller.session(profile_name)
        self._client = session.ssh_client if session else None
        self._timeout = session.profile.ssh_timeout if session else 10
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        back = QPushButton("← Back")
        back.clicked.connect(self.navigator.go_back)
        top.addWidget(back)
        title = QLabel(f"Batch script · {self.job.job_id} · {self.job.name}")
        title.setObjectName("HeaderHost")
        top.addWidget(title, 1)
        save = QPushButton("Save…")
        save.clicked.connect(self._save)
        top.addWidget(save)
        layout.addLayout(top)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(QFont("monospace"))
        self.text.setPlainText("Loading…")
        layout.addWidget(self.text, 1)

    def _load(self) -> None:
        if self._client is None:
            self.text.setPlainText("(no SSH session)")
            return
        client, timeout, job_id = self._client, self._timeout, self.job.job_id

        def _fetch() -> str:
            return client.execute(
                f"scontrol write batch_script {shlex.quote(job_id)} -", timeout
            )

        run_async(_fetch, self._on_loaded, self._on_error)

    def _on_loaded(self, script: str) -> None:
        self.text.setPlainText(
            script or "(no script available — scontrol returned empty)"
        )

    def _on_error(self, exc: Exception) -> None:
        self.text.setPlainText(f"(failed to fetch batch script: {exc})")

    def _save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save batch script", f"{self.job.job_id}.sbatch"
        )
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.text.toPlainText())
