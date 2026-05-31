"""Tests for the Job Detail / Log Viewer / Batch Script sub-views + navigation."""

from slurmhub.gui.main_window import MainWindow
from slurmhub.gui.models.jobs_model import JOB_ROLE
from slurmhub.gui.views.batch_script_view import BatchScriptView
from slurmhub.gui.views.job_detail_view import JobDetailView
from slurmhub.gui.views.log_viewer import LogViewer


class _Nav:
    """Minimal navigator stub for testing a sub-view in isolation."""

    def go_back(self):
        self.went_back = True

    def open_subview(self, widget):
        self.opened = widget


def _refresh(controller, qtbot):
    with qtbot.waitSignal(controller.jobsUpdated, timeout=5000):
        controller.refresh_profile("demo")
    return controller.session("demo")


def _a_job(session, state=None):
    if state:
        return next(j for j in session.jobs if j.state == state)
    return session.jobs[0]


def test_job_detail_loads_details(demo_controller, qtbot):
    session = _refresh(demo_controller, qtbot)
    job = _a_job(session, "RUNNING")
    view = JobDetailView(demo_controller, "demo", job, _Nav())
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: "Loading" not in view.info.text(), timeout=5000)
    assert job.job_id in view.title.text()
    assert "Partition" in view.info.text()


def test_log_viewer_streams_demo_content(demo_controller, qtbot):
    session = _refresh(demo_controller, qtbot)
    job = _a_job(session)
    view = LogViewer(demo_controller, "demo", job, _Nav())
    qtbot.addWidget(view)
    try:
        qtbot.waitUntil(
            lambda: bool(view.text.toPlainText().strip()), timeout=5000
        )
        assert view.text.toPlainText().strip()
    finally:
        view.teardown()


def test_batch_script_view_loads(demo_controller, qtbot):
    session = _refresh(demo_controller, qtbot)
    job = _a_job(session)
    view = BatchScriptView(demo_controller, "demo", job, _Nav())
    qtbot.addWidget(view)
    qtbot.waitUntil(
        lambda: view.text.toPlainText() not in ("", "Loading…"), timeout=5000
    )
    assert "#" in view.text.toPlainText()  # a shell script


def test_navigation_open_and_back(demo_controller, qtbot):
    window = MainWindow(demo_controller)
    qtbot.addWidget(window)
    _refresh(demo_controller, qtbot)
    window.queue_view.reload()

    proxy = window.queue_view.proxy
    window.queue_view.table.setCurrentIndex(proxy.index(0, 0))
    window.queue_view._emit_activated()

    assert isinstance(window.stack.currentWidget(), JobDetailView)
    window.go_back()
    assert window.stack.currentWidget() is window.queue_view


def test_nav_switch_discards_subview(demo_controller, qtbot):
    window = MainWindow(demo_controller)
    qtbot.addWidget(window)
    _refresh(demo_controller, qtbot)
    window.queue_view.reload()
    job = window.queue_view.proxy.data(window.queue_view.proxy.index(0, 0), JOB_ROLE)
    window._open_job_detail(job)
    assert isinstance(window.stack.currentWidget(), JobDetailView)

    # Selecting a nav entry tears the sub-view down and shows a permanent page.
    window.nav_list.setCurrentRow(1)  # Cluster
    assert window.stack.currentWidget() in window._permanent_pages
