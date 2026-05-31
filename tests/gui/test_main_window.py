"""Tests for the main dashboard window: shell construction and navigation."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton

from slurmhub.slurm.demo_data import DEMO_HOST
from slurmhub.gui.main_window import NAV_ITEMS, MainWindow


def test_window_builds_with_all_nav_pages(demo_controller, qtbot):
    window = MainWindow(demo_controller)
    qtbot.addWidget(window)

    assert window.nav_list.count() == len(NAV_ITEMS)
    assert window.stack.count() == len(NAV_ITEMS)
    assert window.header_host.text() == DEMO_HOST


def test_nav_selection_switches_stacked_page(demo_controller, qtbot):
    window = MainWindow(demo_controller)
    qtbot.addWidget(window)

    for row in range(window.nav_list.count()):
        window.nav_list.setCurrentRow(row)
        assert window.stack.currentIndex() == row


def test_queue_view_reflects_demo_jobs(demo_controller, qtbot):
    window = MainWindow(demo_controller)
    qtbot.addWidget(window)

    with qtbot.waitSignal(demo_controller.jobsUpdated, timeout=5000):
        demo_controller.refresh_profile("demo")

    assert window.queue_view.model.rowCount() > 0
    assert window.statusBar().currentMessage()


def test_about_page_exposes_help_actions(demo_controller, qtbot):
    window = MainWindow(demo_controller)
    qtbot.addWidget(window)

    about_row = next(
        i for i, (_label, key, _icon) in enumerate(NAV_ITEMS) if key == "about"
    )
    window.nav_list.setCurrentRow(about_row)

    about_page = window._pages["about"]
    help_text = about_page.findChild(QLabel, "AboutHelpText")
    docs_button = about_page.findChild(QPushButton, "AboutDocsButton")
    settings_button = about_page.findChild(QPushButton, "AboutSettingsButton")

    assert help_text is not None
    assert "Queue" in help_text.text()
    assert docs_button is not None
    assert settings_button is not None


def test_about_page_settings_button_navigates_to_settings(demo_controller, qtbot):
    window = MainWindow(demo_controller)
    qtbot.addWidget(window)

    about_row = next(
        i for i, (_label, key, _icon) in enumerate(NAV_ITEMS) if key == "about"
    )
    settings_row = next(
        i for i, (_label, key, _icon) in enumerate(NAV_ITEMS) if key == "settings"
    )
    window.nav_list.setCurrentRow(about_row)

    about_page = window._pages["about"]
    settings_button = about_page.findChild(QPushButton, "AboutSettingsButton")
    assert settings_button is not None

    qtbot.mouseClick(settings_button, Qt.MouseButton.LeftButton)

    assert window.nav_list.currentRow() == settings_row
    assert window.stack.currentIndex() == settings_row
