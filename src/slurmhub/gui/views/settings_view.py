"""The Settings screen — a GUI proxy for the on-disk TOML config.

Edits a deep copy of the live :class:`AppConfig` and persists it via
``ConfigLoader.save_toml`` (the same writer the wizard uses). Connection/profile
changes take effect on the next launch; theme changes apply immediately.

Known, accepted limitation (inherited from ``save_toml``): SSH passphrases are
never written to disk, and ``[defaults.slurm]`` is not emitted — per-profile
slurm formats still round-trip. This is surfaced as a hint on the screen.
"""

import copy
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from slurmhub.config import (
    AppConfig,
    ConfigLoader,
    DatabaseConfig,
    LogConfig,
    ProfileConfig,
    SlurmConfig,
    SSHConfig,
)
from slurmhub.gui.controller import AppController
from slurmhub.gui.theme import apply_theme, load_theme_preference, save_theme_preference


def _parse_specific_projects(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and value:
            result[key] = value
    return result


def _format_specific_projects(mapping: dict[str, str]) -> str:
    return "\n".join(f"{k} = {v}" for k, v in mapping.items())


class SettingsView(QWidget):
    def __init__(
        self, controller: AppController, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self._working: AppConfig = copy.deepcopy(controller.config)
        self._current_profile: Optional[str] = None

        self._build_ui()
        self._load_profiles_list()
        self._load_database_tab()

    # ── construction ─────────────────────────────────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_profiles_tab(), "Profiles")
        self.tabs.addTab(self._build_database_tab(), "Database")
        self.tabs.addTab(self._build_appearance_tab(), "Appearance")
        layout.addWidget(self.tabs, 1)

        footer = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("HeaderStatus")
        footer.addWidget(self.status, 1)
        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("Primary")
        self.save_button.clicked.connect(self._save)
        footer.addWidget(self.save_button)
        layout.addLayout(footer)

        if self.controller.demo:
            self.save_button.setEnabled(False)
            self.status.setText("Settings are read-only in demo mode.")

    def _build_profiles_tab(self) -> QWidget:
        page = QWidget()
        outer = QHBoxLayout(page)

        left = QVBoxLayout()
        self.profile_list = QListWidget()
        self.profile_list.currentTextChanged.connect(self._on_profile_selected)
        left.addWidget(self.profile_list, 1)
        buttons = QHBoxLayout()
        add = QPushButton("Add")
        add.clicked.connect(self._add_profile)
        remove = QPushButton("Remove")
        remove.clicked.connect(self._remove_profile)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        left.addLayout(buttons)
        outer.addLayout(left, 1)

        form = QFormLayout()
        self.f_name = QLineEdit()
        self.f_host = QLineEdit()
        self.f_username = QLineEdit()
        self.f_port = QSpinBox()
        self.f_port.setRange(1, 65535)
        self.f_key = QLineEdit()
        key_row = QHBoxLayout()
        key_row.addWidget(self.f_key, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_key)
        key_row.addWidget(browse)
        self.f_jump = QLineEdit()
        self.f_log_pattern = QLineEdit()
        self.f_view_cmd = QLineEdit()
        self.f_specific = QPlainTextEdit()
        self.f_specific.setPlaceholderText("project = {work_dir}/logs/{job_id}.out")
        self.f_specific.setMaximumHeight(70)
        self.f_squeue = QLineEdit()
        self.f_sacct = QLineEdit()
        self.f_refresh = QSpinBox()
        self.f_refresh.setRange(1, 3600)
        self.f_sacct_refresh = QSpinBox()
        self.f_sacct_refresh.setRange(1, 86400)
        self.f_timeout = QSpinBox()
        self.f_timeout.setRange(1, 600)

        form.addRow("Name", self.f_name)
        form.addRow("Host", self.f_host)
        form.addRow("Username", self.f_username)
        form.addRow("Port", self.f_port)
        form.addRow("SSH key", key_row)
        form.addRow("Jump host", self.f_jump)
        form.addRow("Log pattern", self.f_log_pattern)
        form.addRow("View command", self.f_view_cmd)
        form.addRow("Per-project logs", self.f_specific)
        form.addRow("squeue format", self.f_squeue)
        form.addRow("sacct format", self.f_sacct)
        form.addRow("Refresh (s)", self.f_refresh)
        form.addRow("sacct refresh (s)", self.f_sacct_refresh)
        form.addRow("SSH timeout (s)", self.f_timeout)

        hint = QLabel(
            "Passphrases are never stored on disk. Changes apply on next launch."
        )
        hint.setObjectName("HeaderStatus")
        hint.setWordWrap(True)

        form_wrap = QVBoxLayout()
        form_wrap.addLayout(form)
        form_wrap.addWidget(hint)
        form_wrap.addStretch(1)
        outer.addLayout(form_wrap, 2)
        return page

    def _build_database_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.db_enabled = QCheckBox("Record job history")
        self.db_path = QLineEdit()
        self.db_path.setPlaceholderText("(default: <config dir>/jobs.db)")
        path_row = QHBoxLayout()
        path_row.addWidget(self.db_path, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_db_path)
        path_row.addWidget(browse)
        self.db_retention = QSpinBox()
        self.db_retention.setRange(0, 3650)
        self.db_retention.setSpecialValueText("keep everything")
        self.db_capture = QCheckBox("Capture measured utilisation")
        self.db_util_interval = QSpinBox()
        self.db_util_interval.setRange(5, 3600)

        form.addRow(self.db_enabled)
        form.addRow("Database path", path_row)
        form.addRow("Retention (days)", self.db_retention)
        form.addRow(self.db_capture)
        form.addRow("Utilisation interval (s)", self.db_util_interval)

        self.cleanup_button = QPushButton("Clean up history now")
        self.cleanup_button.clicked.connect(self._cleanup_history)
        self.cleanup_button.setEnabled(self.controller.database is not None)
        form.addRow(self.cleanup_button)
        return page

    def _build_appearance_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Auto", "Light", "Dark"])
        self.theme_combo.setCurrentText(load_theme_preference().capitalize())
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        form.addRow("Theme", self.theme_combo)

        settings = QSettings("slurmhub", "SlurmHub")
        self.tray_checkbox = QCheckBox("Minimise to system tray on close")
        self.tray_checkbox.setChecked(settings.value("tray/minimize", False, type=bool))
        self.tray_checkbox.toggled.connect(
            lambda on: QSettings("slurmhub", "SlurmHub").setValue("tray/minimize", on)
        )
        form.addRow(self.tray_checkbox)

        self.notify_checkbox = QCheckBox("Notify on job completion / failure")
        self.notify_checkbox.setChecked(
            settings.value("notify/enabled", True, type=bool)
        )
        self.notify_checkbox.toggled.connect(
            lambda on: QSettings("slurmhub", "SlurmHub").setValue("notify/enabled", on)
        )
        form.addRow(self.notify_checkbox)
        return page

    # ── profiles tab logic ───────────────────────────────────────────
    def _load_profiles_list(self) -> None:
        self.profile_list.blockSignals(True)
        self.profile_list.clear()
        self.profile_list.addItems(list(self._working.profiles.keys()))
        self.profile_list.blockSignals(False)
        if self.profile_list.count():
            self.profile_list.setCurrentRow(0)

    def _on_profile_selected(self, name: str) -> None:
        # Commit edits to the previously-selected profile before switching.
        if self._current_profile and self._current_profile in self._working.profiles:
            self._commit_form()
        if not name or name not in self._working.profiles:
            self._current_profile = None
            return
        self._current_profile = name
        self._load_form(self._working.profiles[name])

    def _load_form(self, profile: ProfileConfig) -> None:
        self.f_name.setText(profile.name)
        self.f_host.setText(profile.ssh.host)
        self.f_username.setText(profile.ssh.username)
        self.f_port.setValue(profile.ssh.port)
        self.f_key.setText(profile.ssh.key_filename)
        self.f_jump.setText(profile.ssh.jump_host)
        self.f_log_pattern.setText(profile.log.default_pattern)
        self.f_view_cmd.setText(profile.log.view_command)
        self.f_specific.setPlainText(
            _format_specific_projects(profile.log.specific_projects)
        )
        self.f_squeue.setText(profile.slurm.squeue_format)
        self.f_sacct.setText(profile.slurm.sacct_format)
        self.f_refresh.setValue(profile.refresh_interval)
        self.f_sacct_refresh.setValue(profile.sacct_refresh_interval)
        self.f_timeout.setValue(profile.ssh_timeout)

    def _commit_form(self) -> None:
        """Write the form back into the working config under its (new) name."""
        if self._current_profile is None:
            return
        old_name = self._current_profile
        new_name = self.f_name.text().strip() or old_name
        profile = ProfileConfig(
            name=new_name,
            ssh=SSHConfig(
                host=self.f_host.text().strip(),
                port=self.f_port.value(),
                username=self.f_username.text().strip(),
                key_filename=self.f_key.text().strip(),
                jump_host=self.f_jump.text().strip(),
            ),
            log=LogConfig(
                default_pattern=self.f_log_pattern.text().strip()
                or "{work_dir}/logs/{job_id}.out",
                specific_projects=_parse_specific_projects(
                    self.f_specific.toPlainText()
                ),
                view_command=self.f_view_cmd.text().strip() or "tail -f {log_path}",
            ),
            slurm=SlurmConfig(
                squeue_format=self.f_squeue.text().strip() or "%i|%j|%T|%M|%Z",
                sacct_format=self.f_sacct.text().strip()
                or "JobID,JobName,State,Elapsed,WorkDir",
            ),
            refresh_interval=self.f_refresh.value(),
            sacct_refresh_interval=self.f_sacct_refresh.value(),
            ssh_timeout=self.f_timeout.value(),
        )
        # Rebuild the dict preserving order, applying any rename.
        rebuilt: dict[str, ProfileConfig] = {}
        for key, value in self._working.profiles.items():
            if key == old_name:
                rebuilt[new_name] = profile
            else:
                rebuilt[key] = value
        self._working.profiles = rebuilt
        self._current_profile = new_name

    def _add_profile(self) -> None:
        base, i = "cluster", 1
        name = base
        while name in self._working.profiles:
            i += 1
            name = f"{base}{i}"
        self._working.profiles[name] = ProfileConfig(name=name)
        self.profile_list.addItem(name)
        self.profile_list.setCurrentRow(self.profile_list.count() - 1)

    def _remove_profile(self) -> None:
        name = (
            self.profile_list.currentItem().text()
            if self.profile_list.currentItem()
            else None
        )
        if not name or name not in self._working.profiles:
            return
        if len(self._working.profiles) <= 1:
            QMessageBox.information(
                self, "Settings", "At least one profile is required."
            )
            return
        del self._working.profiles[name]
        self._current_profile = None
        self._load_profiles_list()

    def _browse_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select SSH key")
        if path:
            self.f_key.setText(path)

    # ── database tab logic ───────────────────────────────────────────
    def _load_database_tab(self) -> None:
        db = self._working.database
        self.db_enabled.setChecked(db.enabled)
        self.db_path.setText(db.path)
        self.db_retention.setValue(db.retention_days)
        self.db_capture.setChecked(db.capture_utilization)
        self.db_util_interval.setValue(db.utilization_interval)

    def _commit_database(self) -> None:
        self._working.database = DatabaseConfig(
            enabled=self.db_enabled.isChecked(),
            path=self.db_path.text().strip(),
            retention_days=self.db_retention.value(),
            capture_utilization=self.db_capture.isChecked(),
            utilization_interval=self.db_util_interval.value(),
        )

    def _browse_db_path(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "History database", filter="SQLite (*.db)"
        )
        if path:
            self.db_path.setText(path)

    def _cleanup_history(self) -> None:
        days = self.db_retention.value()
        if days <= 0:
            QMessageBox.information(
                self,
                "Clean up history",
                "Set a retention window (> 0 days) to prune old runs.",
            )
            return
        removed = self.controller.prune_history(days)
        self.status.setText(f"Removed {removed} old run(s).")

    # ── appearance tab logic ─────────────────────────────────────────
    def _on_theme_changed(self, label: str) -> None:
        mode = label.lower()
        save_theme_preference(mode)
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            apply_theme(app, mode)

    def _validate_profiles(self) -> Optional[str]:
        for name, profile in self._working.profiles.items():
            if not profile.ssh.host.strip():
                return (
                    f"Profile '{name}' is missing the SSH host. "
                    "Set Host before saving."
                )

            key_file = profile.ssh.key_filename.strip()
            if key_file:
                key_path = Path(key_file).expanduser()
                if not key_path.exists():
                    return (
                        f"Profile '{name}' references SSH key '{key_file}', "
                        "but that path does not exist."
                    )
                if not key_path.is_file():
                    return (
                        f"Profile '{name}' references SSH key '{key_file}', "
                        "but that path is not a file."
                    )
        return None

    # ── save ─────────────────────────────────────────────────────────
    def _save(self) -> None:
        self._commit_form()
        self._commit_database()
        validation_error = self._validate_profiles()
        if validation_error:
            QMessageBox.warning(self, "Invalid profile settings", validation_error)
            self.status.setText("Fix profile validation errors before saving.")
            return

        config = AppConfig(
            profiles=self._working.profiles, database=self._working.database
        )
        path = self.controller.config_path or ConfigLoader.get_default_config_path()
        try:
            ConfigLoader.save_toml(config, path)
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.controller.config = config
        self.status.setText(
            f"Saved to {path}. Restart to apply connection/profile changes."
        )
