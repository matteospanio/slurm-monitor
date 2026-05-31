"""Streaming log viewer (``tail -f`` over SSH).

A long-lived :class:`LogStreamer` ``QThread`` runs ``SSHClient.stream_command``
and emits each line to the UI thread. Follow mode auto-scrolls; a search box
finds matches. ``teardown()`` stops the stream and is called by the navigator
on back / window close.
"""

from typing import Optional

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QFont, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from slurmhub.qt.controller import AppController
from slurmhub.squeue_parser import SlurmJob


class LogStreamer(QThread):
    """Runs a streaming SSH command, emitting one signal per output line."""

    line = Signal(str)

    def __init__(self, client, command: str, timeout: int, parent=None) -> None:
        super().__init__(parent)
        self._client = client
        self._command = command
        self._timeout = timeout
        self._stop = False

    def run(self) -> None:
        try:
            self._client.stream_command(
                self._command,
                on_line=self.line.emit,
                should_stop=lambda: self._stop,
                timeout=self._timeout,
            )
        except Exception as exc:  # noqa: BLE001 — shown in the log pane
            self.line.emit(f"[stream error: {exc}]")

    def stop(self) -> None:
        self._stop = True


class LogViewer(QWidget):
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
        self.log_path = (
            session.path_resolver.resolve_path(job.job_id, job.work_dir)
            if session
            else ""
        )
        self._streamer: Optional[LogStreamer] = None
        self._build_ui()
        self._start_stream()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        back = QPushButton("← Back")
        back.clicked.connect(self.navigator.go_back)
        top.addWidget(back)
        title = QLabel(f"Log · {self.job.job_id} · {self.log_path}")
        title.setObjectName("HeaderHost")
        top.addWidget(title, 1)
        layout.addLayout(top)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(20000)
        self.text.setFont(QFont("monospace"))
        layout.addWidget(self.text, 1)

        controls = QHBoxLayout()
        self.follow = QCheckBox("Follow")
        self.follow.setChecked(True)
        controls.addWidget(self.follow)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")
        self.search.returnPressed.connect(self._find_next)
        controls.addWidget(self.search, 1)
        prev_btn = QPushButton("Prev")
        prev_btn.clicked.connect(self._find_prev)
        next_btn = QPushButton("Next")
        next_btn.clicked.connect(self._find_next)
        save_btn = QPushButton("Save…")
        save_btn.clicked.connect(self._save)
        copy_btn = QPushButton("Copy path")
        copy_btn.clicked.connect(self._copy_path)
        for b in (prev_btn, next_btn, save_btn, copy_btn):
            controls.addWidget(b)
        layout.addLayout(controls)

    # ── streaming ────────────────────────────────────────────────────
    def _start_stream(self) -> None:
        if self._client is None:
            self.text.appendPlainText("(no SSH session)")
            return
        command = f"tail -n 50 -f {self.log_path}"
        self._streamer = LogStreamer(self._client, command, self._timeout)
        self._streamer.line.connect(self._append_line)
        self._streamer.start()

    def _append_line(self, text: str) -> None:
        self.text.appendPlainText(text)
        if self.follow.isChecked():
            self.text.verticalScrollBar().setValue(
                self.text.verticalScrollBar().maximum()
            )

    def teardown(self) -> None:
        if self._streamer is not None:
            self._streamer.stop()
            self._streamer.wait(2000)
            self._streamer = None

    # ── search / save ────────────────────────────────────────────────
    def _find_next(self) -> None:
        if self.search.text():
            self.text.find(self.search.text())

    def _find_prev(self) -> None:
        if self.search.text():
            self.text.find(
                self.search.text(), QTextDocument.FindFlag.FindBackward
            )

    def _save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save log", f"{self.job.job_id}.log")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.text.toPlainText())

    def _copy_path(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.log_path)
