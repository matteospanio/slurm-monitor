"""The main dashboard window: sidebar shell + stacked screens.

Phase 0 wires the shell (sidebar nav, profile switcher, header connection
strip, status bar, docs link) with placeholder pages. Later phases replace the
placeholders with the real Queue / Cluster / History / Settings views; the
shell, routing, and signal plumbing stay.
"""

from importlib.metadata import PackageNotFoundError, version
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from slurmhub.qt.controller import AppController
from slurmhub.qt.views.cluster_view import ClusterView
from slurmhub.qt.views.history_view import HistoryView
from slurmhub.qt.views.queue_view import QueueView
from slurmhub.qt.views.settings_view import SettingsView

DOCS_URL = "https://matteospanio.github.io/slurmhub/"

# (label, page key) in sidebar order.
NAV_ITEMS = [
    ("Queue", "queue"),
    ("Cluster", "cluster"),
    ("History", "history"),
    ("Settings", "settings"),
    ("About", "about"),
]


def _app_version() -> str:
    try:
        return version("slurmhub")
    except PackageNotFoundError:  # pragma: no cover — running from a checkout
        return "dev"


def _placeholder(title: str, subtitle: str = "") -> QWidget:
    """A simple centred placeholder page used until a real view lands."""
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    heading = QLabel(title)
    heading.setStyleSheet("font-size: 18pt; font-weight: bold;")
    heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(heading)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setObjectName("HeaderStatus")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)
    return page


class MainWindow(QMainWindow):
    def __init__(
        self, controller: AppController, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self._pages: dict[str, QWidget] = {}
        self._nav_stack: list[QWidget] = []  # sub-view back stack
        self.setWindowTitle("SlurmHub")
        self.resize(1120, 720)
        self.setMinimumSize(860, 540)
        self._build_ui()
        self._connect_signals()
        self._sync_active_profile_view()

    # ── construction ─────────────────────────────────────────────────
    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self._build_header())

        self.stack = QStackedWidget()
        self._build_pages()
        right_layout.addWidget(self.stack, 1)

        root.addWidget(right, 1)
        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar())

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(216)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        brand = QLabel("SlurmHub")
        brand.setObjectName("SidebarBrand")
        layout.addWidget(brand)

        self.profile_switcher = QComboBox()
        self.profile_switcher.setObjectName("ProfileSwitcher")
        self.profile_switcher.addItems(self.controller.profile_names)
        if self.controller.active_profile:
            self.profile_switcher.setCurrentText(self.controller.active_profile)
        self.profile_switcher.setEnabled(len(self.controller.profile_names) > 1)
        layout.addWidget(self.profile_switcher)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("NavList")
        for label, key in NAV_ITEMS:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.nav_list.addItem(item)
        self.nav_list.setCurrentRow(0)
        layout.addWidget(self.nav_list)

        layout.addStretch(1)

        docs = QPushButton("\U0001F4D6  Documentation")
        docs.setObjectName("DocsLink")
        docs.setCursor(Qt.CursorShape.PointingHandCursor)
        docs.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DOCS_URL)))
        layout.addWidget(docs)

        version_label = QLabel(f"v{_app_version()}")
        version_label.setObjectName("VersionLabel")
        layout.addWidget(version_label)

        return sidebar

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("HeaderStrip")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)

        self.header_host = QLabel("")
        self.header_host.setObjectName("HeaderHost")
        layout.addWidget(self.header_host)

        layout.addStretch(1)

        self.header_status = QLabel("")
        self.header_status.setObjectName("HeaderStatus")
        layout.addWidget(self.header_status)

        return header

    def _build_pages(self) -> None:
        self.queue_view = QueueView(self.controller)
        self._pages["queue"] = self.queue_view

        self.cluster_view = ClusterView(self.controller)
        self._pages["cluster"] = self.cluster_view

        self.history_view = HistoryView(self.controller)
        self._pages["history"] = self.history_view

        self.settings_view = SettingsView(self.controller)
        self._pages["settings"] = self.settings_view
        self._pages["about"] = _placeholder(
            "SlurmHub", f"v{_app_version()} · {DOCS_URL}"
        )

        for _label, key in NAV_ITEMS:
            self.stack.addWidget(self._pages[key])
        # The permanent nav pages are never torn down by go_back().
        self._permanent_pages = set(self._pages.values())

    # ── sub-view navigation ──────────────────────────────────────────
    def open_subview(self, widget: QWidget) -> None:
        """Push a transient full-page sub-view (Job Detail / Log / Batch)."""
        self._nav_stack.append(self.stack.currentWidget())
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)

    def go_back(self) -> None:
        current = self.stack.currentWidget()
        target = self._nav_stack.pop() if self._nav_stack else self.stack.widget(0)
        self.stack.setCurrentWidget(target)
        if current is not None and current not in self._permanent_pages:
            if hasattr(current, "teardown"):
                current.teardown()
            self.stack.removeWidget(current)
            current.deleteLater()

    def _open_job_detail(self, job) -> None:
        from slurmhub.qt.views.job_detail_view import JobDetailView

        profile = self.controller.active_profile
        if profile is None:
            return
        self.open_subview(JobDetailView(self.controller, profile, job, self))

    def _on_nav_changed(self, row: int) -> None:
        if row < 0:
            return
        self._discard_subviews()
        self.stack.setCurrentIndex(row)

    def _discard_subviews(self) -> None:
        """Tear down and remove every transient sub-view; clear the back stack."""
        self._nav_stack.clear()
        for i in reversed(range(self.stack.count())):
            widget = self.stack.widget(i)
            if widget not in self._permanent_pages:
                if hasattr(widget, "teardown"):
                    widget.teardown()
                self.stack.removeWidget(widget)
                widget.deleteLater()

    def closeEvent(self, event) -> None:
        # Stop any open log stream before the app tears down.
        self._discard_subviews()
        super().closeEvent(event)

    # ── signals ──────────────────────────────────────────────────────
    def _connect_signals(self) -> None:
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        self.queue_view.jobActivated.connect(self._open_job_detail)
        self.profile_switcher.currentTextChanged.connect(self._on_profile_changed)
        self.controller.connectionChanged.connect(self._on_connection_changed)
        self.controller.jobsUpdated.connect(self._on_jobs_updated)
        self.controller.fetchFailed.connect(self._on_fetch_failed)
        self.controller.jobActionFinished.connect(self._on_job_action_finished)
        self.controller.authRequired.connect(self._on_auth_required)

    def _on_profile_changed(self, name: str) -> None:
        if not name:
            return
        self.controller.set_active_profile(name)
        self._sync_active_profile_view()

    def _on_connection_changed(self, name: str) -> None:
        if name == self.controller.active_profile:
            self._update_header()

    def _on_jobs_updated(self, name: str) -> None:
        if name == self.controller.active_profile:
            self._update_status_bar()

    def _on_fetch_failed(self, name: str, message: str) -> None:
        self.statusBar().showMessage(f"[{name}] {message}", 8000)

    def _on_auth_required(self, name: str) -> None:
        from PySide6.QtWidgets import QInputDialog, QLineEdit as _QLineEdit

        session = self.controller.session(name)
        host = session.profile.ssh.host if session else name
        password, ok = QInputDialog.getText(
            self,
            "SSH authentication",
            f"Password or key passphrase for {host}:",
            _QLineEdit.EchoMode.Password,
        )
        if ok and password:
            self.controller.submit_credentials(name, password)

    def _on_job_action_finished(
        self, name: str, job_id: str, verb: str, ok: bool, message: str
    ) -> None:
        if ok:
            self.statusBar().showMessage(f"{verb} {job_id}: ok", 4000)
        else:
            self.statusBar().showMessage(
                f"{verb} {job_id} failed: {message}", 8000
            )

    # ── view sync ────────────────────────────────────────────────────
    def _sync_active_profile_view(self) -> None:
        self._update_header()
        self._update_status_bar()

    def _update_header(self) -> None:
        session = self.controller.session()
        if session is None:
            return
        self.header_host.setText(session.profile.ssh.host)
        if session.error_message:
            text, state = f"✕ {session.error_message}", "error"
        elif session.is_loading:
            text, state = "↻ refreshing…", "loading"
        elif session.last_updated:
            text, state = f"✓ updated {session.last_updated}", "ok"
        else:
            text, state = "connecting…", "loading"
        self.header_status.setText(text)
        self.header_status.setProperty("state", state)
        # Re-polish so the [state="..."] QSS selector re-applies.
        self.header_status.style().unpolish(self.header_status)
        self.header_status.style().polish(self.header_status)

    def _update_status_bar(self) -> None:
        session = self.controller.session()
        if session is None:
            return
        total = len(session.jobs)
        running = sum(1 for j in session.jobs if j.state == "RUNNING")
        pending = sum(1 for j in session.jobs if j.state == "PENDING")
        msg = f"{total} jobs  •  {running} running  •  {pending} pending"
        if session.partial_errors:
            msg += f"  •  partial: {', '.join(sorted(session.partial_errors))}"
        self.statusBar().showMessage(msg)
