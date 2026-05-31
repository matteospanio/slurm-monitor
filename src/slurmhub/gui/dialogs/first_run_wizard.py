"""First-run setup dialog for the GUI.

Collects a single cluster profile (more can be added later in Settings), can
test the SSH connection on a worker thread, and saves the config via
``ConfigLoader.save_toml`` — the GUI counterpart of the Textual
``run_first_run_wizard`` used by ``--tui``.
"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from slurmhub.config import AppConfig, ConfigLoader, LogConfig, ProfileConfig, SSHConfig
from slurmhub.gui.workers import FetchTask
from slurmhub.slurm.ssh import SSHClient


class FirstRunWizard(QDialog):
    def __init__(self, default_name: str = "default", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("SlurmHub — first-run setup")
        self.setMinimumWidth(440)
        self._build_ui(default_name)

    def _build_ui(self, default_name: str) -> None:
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Connect SlurmHub to a Slurm cluster over SSH. Key-based auth is "
            "recommended; you'll be prompted for a password if needed."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.name = QLineEdit(default_name)
        self.host = QLineEdit()
        self.host.setPlaceholderText("login.cluster.example.org")
        self.username = QLineEdit()
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(22)
        self.key = QLineEdit()
        key_row = QHBoxLayout()
        key_row.addWidget(self.key, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_key)
        key_row.addWidget(browse)
        self.log_pattern = QLineEdit("{work_dir}/logs/{job_id}.out")

        form.addRow("Profile name", self.name)
        form.addRow("Host", self.host)
        form.addRow("Username", self.username)
        form.addRow("Port", self.port)
        form.addRow("SSH key", key_row)
        form.addRow("Log pattern", self.log_pattern)
        layout.addLayout(form)

        test_row = QHBoxLayout()
        self.test_button = QPushButton("Test connection")
        self.test_button.clicked.connect(self._test_connection)
        test_row.addWidget(self.test_button)
        self.test_result = QLabel("")
        self.test_result.setObjectName("HeaderStatus")
        test_row.addWidget(self.test_result, 1)
        layout.addLayout(test_row)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self._accept_if_valid)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.host.textChanged.connect(self._update_ok_enabled)
        self._update_ok_enabled()

    def _browse_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select SSH key")
        if path:
            self.key.setText(path)

    def _update_ok_enabled(self) -> None:
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(
            bool(self.host.text().strip())
        )

    def profile(self) -> ProfileConfig:
        return ProfileConfig(
            name=self.name.text().strip() or "default",
            ssh=SSHConfig(
                host=self.host.text().strip() or "localhost",
                port=self.port.value(),
                username=self.username.text().strip(),
                key_filename=self.key.text().strip(),
            ),
            log=LogConfig(
                default_pattern=self.log_pattern.text().strip()
                or "{work_dir}/logs/{job_id}.out"
            ),
        )

    # ── connection test (worker thread) ──────────────────────────────
    def _test_connection(self) -> None:
        self.test_button.setEnabled(False)
        self.test_result.setText("Testing…")
        profile = self.profile()

        def _run() -> bool:
            client = SSHClient(profile.ssh)
            try:
                return client.check_connection(timeout=10)
            finally:
                client.close()

        task = FetchTask(_run)
        task.signals.finished.connect(self._on_test_result)
        task.signals.failed.connect(self._on_test_failed)
        from PySide6.QtCore import QThreadPool

        QThreadPool.globalInstance().start(task)

    def _on_test_result(self, ok: bool) -> None:
        self.test_button.setEnabled(True)
        self.test_result.setText("✓ Connected" if ok else "✕ Could not connect")

    def _on_test_failed(self, exc: Exception) -> None:
        self.test_button.setEnabled(True)
        self.test_result.setText(f"✕ {exc}")

    def _accept_if_valid(self) -> None:
        if self.host.text().strip():
            self.accept()


def run_first_run_wizard_qt(save_path: Path) -> Optional[AppConfig]:
    """Show the wizard; on Save, persist + return the config, else ``None``.

    Reuses (or creates) the singleton ``QApplication`` so the main window can
    adopt it afterwards.
    """
    from PySide6.QtWidgets import QApplication

    from slurmhub.gui.theme import apply_theme, load_theme_preference

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("SlurmHub")
    app.setOrganizationName("slurmhub")
    apply_theme(app, load_theme_preference())

    dialog = FirstRunWizard()
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None

    profile = dialog.profile()
    config = AppConfig(profiles={profile.name: profile})
    ConfigLoader.save_toml(config, save_path)
    return config
