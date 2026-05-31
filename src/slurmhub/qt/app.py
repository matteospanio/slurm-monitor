"""QApplication bootstrap for the slurmhub desktop GUI."""

from pathlib import Path
from typing import Optional

from slurmhub.config import AppConfig
from slurmhub.db import Database


def run_gui(
    app_config: AppConfig,
    demo: bool = False,
    database: Optional[Database] = None,
    config_path: Optional[Path] = None,
) -> int:
    """Launch the Qt GUI and block until the window is closed.

    Builds the :class:`QApplication`, applies the saved theme, wires the
    :class:`AppController` to the :class:`MainWindow`, starts periodic refresh,
    and tears everything down on exit. Returns the Qt exit code.
    """
    from PySide6.QtWidgets import QApplication

    from slurmhub.qt.controller import AppController
    from slurmhub.qt.main_window import MainWindow
    from slurmhub.qt.theme import apply_theme, load_theme_preference

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("SlurmHub")
    app.setApplicationDisplayName("SlurmHub")
    app.setOrganizationName("slurmhub")

    apply_theme(app, load_theme_preference())

    controller = AppController(
        app_config, demo=demo, database=database, config_path=config_path
    )
    window = MainWindow(controller)
    window.show()
    controller.start()

    try:
        exit_code = app.exec()
    finally:
        controller.shutdown()
    return exit_code
