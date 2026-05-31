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


def _detail_rows(view):
    rows = {}
    for i in range(view.details_table.rowCount()):
        key_item = view.details_table.item(i, 0)
        value_item = view.details_table.item(i, 1)
        if key_item is None or value_item is None:
            continue
        rows[key_item.text()] = value_item.text()
    return rows


def test_job_detail_loads_details(demo_controller, qtbot):
    session = _refresh(demo_controller, qtbot)
    job = _a_job(session, "RUNNING")
    view = JobDetailView(demo_controller, "demo", job, _Nav())
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view.details_table.rowCount() > 0, timeout=5000)
    rows = _detail_rows(view)
    assert job.job_id in view.title.text()
    assert "Partition" in rows


def test_job_detail_opens_log_with_scontrol_path(demo_controller, qtbot, monkeypatch):
    session = _refresh(demo_controller, qtbot)
    job = _a_job(session, "RUNNING")
    nav = _Nav()
    view = JobDetailView(demo_controller, "demo", job, nav)
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view.details_table.rowCount() > 0, timeout=5000)
    monkeypatch.setattr(LogViewer, "_start_stream", lambda self: None)

    view._open_log()

    assert isinstance(nav.opened, LogViewer)
    assert nav.opened.log_path == view._stdout_path


def test_job_detail_falls_back_to_persisted_history(
    demo_controller, qtbot, monkeypatch
):
    session = _refresh(demo_controller, qtbot)
    job = next((j for j in session.jobs if j.state == "COMPLETED"), session.jobs[0])
    monkeypatch.setattr(
        "slurmhub.gui.views.job_detail_view.fetch_job_details",
        lambda *_args, **_kwargs: None,
    )

    view = JobDetailView(demo_controller, "demo", job, _Nav())
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view.details_table.rowCount() > 0, timeout=5000)

    assert "persisted history from the local database" in view.details_status.text()
    assert "No live or persisted detail data" not in view.details_status.text()


def test_log_viewer_streams_demo_content(demo_controller, qtbot):
    session = _refresh(demo_controller, qtbot)
    job = _a_job(session)
    view = LogViewer(demo_controller, "demo", job, _Nav())
    qtbot.addWidget(view)
    try:
        qtbot.waitUntil(lambda: bool(view.text.toPlainText().strip()), timeout=5000)
        assert view.text.toPlainText().strip()
    finally:
        view.teardown()


def test_log_viewer_prefers_explicit_log_path(demo_controller, qtbot, monkeypatch):
    session = _refresh(demo_controller, qtbot)
    job = _a_job(session)
    monkeypatch.setattr(LogViewer, "_start_stream", lambda self: None)

    view = LogViewer(
        demo_controller,
        "demo",
        job,
        _Nav(),
        log_path="/tmp/from-scontrol.out",
    )
    qtbot.addWidget(view)

    assert view.log_path == "/tmp/from-scontrol.out"
    assert view._build_stream_command() == "tail -n 50 -f /tmp/from-scontrol.out"


def test_log_viewer_uses_configured_command_template(
    demo_controller, qtbot, monkeypatch
):
    session = _refresh(demo_controller, qtbot)
    session.profile.log.view_command = "less +F {log_path}"
    job = _a_job(session)
    monkeypatch.setattr(LogViewer, "_start_stream", lambda self: None)

    view = LogViewer(
        demo_controller,
        "demo",
        job,
        _Nav(),
        log_path="/tmp/logs with space.out",
    )
    qtbot.addWidget(view)

    assert view._build_stream_command() == "less +F '/tmp/logs with space.out'"


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
