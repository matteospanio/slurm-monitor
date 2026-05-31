"""The main dashboard window: sidebar shell + stacked screens.

Phase 0 wires the shell (sidebar nav, profile switcher, header connection
strip, status bar, docs link) with placeholder pages. Later phases replace the
placeholders with the real Queue / Cluster / History / Settings views; the
shell, routing, and signal plumbing stay.
"""

from importlib.metadata import PackageNotFoundError, version
from typing import Optional

from PySide6.QtCore import QSettings, QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from slurmhub.gui.branding import app_icon
from slurmhub.gui.controller import AppController
from slurmhub.gui.icons import button_icon, nav_icon
from slurmhub.gui.views.cluster_view import ClusterView
from slurmhub.gui.views.history_view import HistoryView
from slurmhub.gui.views.queue_view import QueueView
from slurmhub.gui.views.settings_view import SettingsView

DOCS_URL = "https://matteospanio.github.io/slurmhub/"

# (label, page key, FontAwesome icon) in sidebar order.
NAV_ITEMS = [
    ("Queue", "queue", "fa5s.list-ul"),
    ("Cluster", "cluster", "fa5s.server"),
    ("History", "history", "fa5s.history"),
    ("Settings", "settings", "fa5s.cog"),
    ("About", "about", "fa5s.info-circle"),
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
        self._force_quit = False
        self._tray_hint_shown = False
        self.setWindowTitle("SlurmHub")
        self.setWindowIcon(app_icon())
        self.resize(1120, 720)
        self.setMinimumSize(860, 540)
        self._build_ui()
        self._tray = self._build_tray()
        self._connect_signals()
        self._sync_active_profile_view()
        self._start_update_check()

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
        right_layout.addWidget(self._build_update_banner())
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
        self.nav_list.setIconSize(QSize(16, 16))
        # Few, fixed entries: never scroll. Letting the list fill the space
        # below the switcher (stretch 1) keeps its viewport >= its content.
        self.nav_list.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.nav_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        for label, key, icon_name in NAV_ITEMS:
            item = QListWidgetItem(nav_icon(icon_name), label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.nav_list.addItem(item)
        self.nav_list.setCurrentRow(0)
        layout.addWidget(self.nav_list, 1)

        docs = QPushButton("  Documentation")
        docs.setObjectName("DocsLink")
        docs.setIcon(button_icon("fa5s.book"))
        docs.setCursor(Qt.CursorShape.PointingHandCursor)
        docs.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DOCS_URL)))
        layout.addWidget(docs)

        version_label = QLabel(f"v{_app_version()}")
        version_label.setObjectName("VersionLabel")
        layout.addWidget(version_label)

        return sidebar

    def _build_update_banner(self) -> QWidget:
        self.update_banner = QFrame()
        self.update_banner.setObjectName("UpdateBanner")
        layout = QHBoxLayout(self.update_banner)
        layout.setContentsMargins(12, 6, 12, 6)
        self.update_label = QLabel("")
        self.update_label.setObjectName("HeaderHost")
        self.update_label.setOpenExternalLinks(True)
        layout.addWidget(self.update_label, 1)
        dismiss = QPushButton("✕")
        dismiss.setFlat(True)
        dismiss.clicked.connect(self.update_banner.hide)
        layout.addWidget(dismiss)
        self.update_banner.hide()
        return self.update_banner

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

        for _label, key, _icon in NAV_ITEMS:
            self.stack.addWidget(self._pages[key])
        # The permanent nav pages are never torn down by go_back().
        self._permanent_pages = set(self._pages.values())

    # ── system tray ──────────────────────────────────────────────────
    def _build_tray(self) -> "QSystemTrayIcon | None":
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        tray = QSystemTrayIcon(app_icon(), self)
        tray.setToolTip("SlurmHub")
        menu = QMenu()
        menu.addAction("Show / Hide", self._toggle_visible)
        menu.addAction("Refresh now", self.controller.force_refresh_active)
        menu.addSeparator()
        menu.addAction("Quit", self._quit)
        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        return tray

    def _toggle_visible(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def _on_tray_activated(self, reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def _quit(self) -> None:
        self._force_quit = True
        self.close()

    # ── update check ─────────────────────────────────────────────────
    def _start_update_check(self) -> None:
        if self.controller.demo:
            return
        from slurmhub.gui.updater import check_for_update, current_version
        from slurmhub.gui.workers import run_async

        version_str = current_version()
        run_async(
            lambda: check_for_update(version_str), self._on_update_check
        )

    def _on_update_check(self, info) -> None:
        if info is None:
            return
        self.update_label.setText(
            f"A new version <b>{info.version}</b> is available — "
            f'<a href="{info.url}">Download</a>'
        )
        self.update_banner.show()

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
        from slurmhub.gui.views.job_detail_view import JobDetailView

        profile = self.controller.active_profile
        if profile is None:
            return
        self.open_subview(JobDetailView(self.controller, profile, job, self))

    def _open_log(self, job) -> None:
        from slurmhub.gui.views.log_viewer import LogViewer

        profile = self.controller.active_profile
        if profile is None or job is None:
            return
        self.open_subview(LogViewer(self.controller, profile, job, self))

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

    def _on_jobs_finished(self, name: str, transitions: list) -> None:
        if not transitions:
            return
        settings = QSettings("slurmhub", "SlurmHub")
        if len(transitions) == 1:
            job_id, job_name, state = transitions[0]
            title = f"Job {job_id} {state.lower()}"
            body = job_name
        else:
            title = f"{len(transitions)} jobs finished"
            body = ", ".join(
                f"{jid} {state.lower()}" for jid, _n, state in transitions[:5]
            )
        self.statusBar().showMessage(f"{title} — {body}", 8000)
        if (
            self._tray is not None
            and settings.value("notify/enabled", True, type=bool)
        ):
            self._tray.showMessage(title, body)

    def closeEvent(self, event) -> None:
        minimize = QSettings("slurmhub", "SlurmHub").value(
            "tray/minimize", False, type=bool
        )
        if minimize and self._tray is not None and not self._force_quit:
            event.ignore()
            self.hide()
            if not self._tray_hint_shown:
                self._tray.showMessage(
                    "SlurmHub",
                    "Still running in the tray — right-click the icon to quit.",
                )
                self._tray_hint_shown = True
            return
        # Stop any open log stream before the app tears down.
        self._discard_subviews()
        super().closeEvent(event)

    # ── signals ──────────────────────────────────────────────────────
    def _connect_signals(self) -> None:
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        self.queue_view.jobActivated.connect(self._open_job_detail)
        self.queue_view.logRequested.connect(self._open_log)
        self.profile_switcher.currentTextChanged.connect(self._on_profile_changed)
        self.controller.connectionChanged.connect(self._on_connection_changed)
        self.controller.jobsUpdated.connect(self._on_jobs_updated)
        self.controller.fetchFailed.connect(self._on_fetch_failed)
        self.controller.jobActionFinished.connect(self._on_job_action_finished)
        self.controller.authRequired.connect(self._on_auth_required)
        self.controller.jobsFinished.connect(self._on_jobs_finished)

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
        elif session.is_cached:
            text, state = f"⤓ cached {session.last_updated} · refreshing…", "loading"
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
