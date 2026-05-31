"""Tests for the main dashboard window: shell construction and navigation."""

from slurmhub.demo_data import DEMO_HOST
from slurmhub.qt.main_window import NAV_ITEMS, MainWindow


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


def test_queue_placeholder_reflects_demo_jobs(demo_controller, qtbot):
    window = MainWindow(demo_controller)
    qtbot.addWidget(window)

    with qtbot.waitSignal(demo_controller.jobsUpdated, timeout=5000):
        demo_controller.refresh_profile("demo")

    assert "jobs" in window.queue_status.text()
    assert window.statusBar().currentMessage()
