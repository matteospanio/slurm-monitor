"""Tests for the Queue view: population, filtering, selection, and scancel."""

from slurmhub.gui.views.queue_view import QueueView


def _populate(controller, qtbot):
    with qtbot.waitSignal(controller.jobsUpdated, timeout=5000):
        controller.refresh_profile("demo")


def test_queue_populates_from_demo(demo_controller, qtbot):
    view = QueueView(demo_controller)
    qtbot.addWidget(view)
    _populate(demo_controller, qtbot)
    view.reload()
    assert view.model.rowCount() > 0
    assert "Queue:" in view.summary.text()


def test_state_filter_reduces_rows(demo_controller, qtbot):
    view = QueueView(demo_controller)
    qtbot.addWidget(view)
    _populate(demo_controller, qtbot)
    view.reload()
    total = view.model.rowCount()

    # Index 1 == "Running" in _STATE_FILTERS.
    view.state_filter.setCurrentIndex(1)
    running = view.model.rowCount()
    session = demo_controller.session("demo")
    assert session.state_filter == "RUNNING"
    assert 0 < running <= total
    assert all(view.model.job_at(r).state == "RUNNING" for r in range(running))


def test_search_filters_by_name_or_id(demo_controller, qtbot):
    view = QueueView(demo_controller)
    qtbot.addWidget(view)
    _populate(demo_controller, qtbot)
    view.reload()

    first = view.model.job_at(0)
    view.search.setText(first.job_id)
    assert view.model.rowCount() >= 1
    assert any(
        view.model.job_at(r).job_id == first.job_id
        for r in range(view.model.rowCount())
    )


def _select_proxy_row(view, row: int) -> None:
    """Select a row by its *proxy* index (what the table actually shows)."""
    view.table.setCurrentIndex(view.proxy.index(row, 0))


def _find_running_proxy_row(view):
    from slurmhub.gui.models.jobs_model import JOB_ROLE

    for r in range(view.proxy.rowCount()):
        job = view.proxy.data(view.proxy.index(r, 0), JOB_ROLE)
        if job is not None and job.state == "RUNNING":
            return r
    return None


def test_cancel_button_disabled_for_terminal_jobs(demo_controller, qtbot):
    view = QueueView(demo_controller)
    qtbot.addWidget(view)
    _populate(demo_controller, qtbot)
    view.reload()

    _select_proxy_row(view, 0)
    job = view.selected_job()
    expected = job is not None and job.state not in {
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        "TIMEOUT",
    }
    assert view.cancel_button.isEnabled() == expected


def test_cancel_job_runs_through_controller(demo_controller, qtbot, monkeypatch):
    # Cancelling a running demo job emits jobActionFinished(ok=True); the demo
    # SSH client treats scancel as a no-op success.
    monkeypatch.setattr("slurmhub.gui.views.queue_view.confirm", lambda *a, **k: True)
    view = QueueView(demo_controller)
    qtbot.addWidget(view)
    _populate(demo_controller, qtbot)
    view.reload()

    running_row = _find_running_proxy_row(view)
    assert running_row is not None
    _select_proxy_row(view, running_row)
    assert view.selected_job().state == "RUNNING"

    with qtbot.waitSignal(demo_controller.jobActionFinished, timeout=5000) as blocker:
        view._cancel_selected()
    _profile, _job_id, verb, ok, _msg = blocker.args
    assert verb == "cancel" and ok is True


def test_scope_toggle_switches_to_cluster_queue_mode(demo_controller, qtbot):
    view = QueueView(demo_controller)
    qtbot.addWidget(view)
    _populate(demo_controller, qtbot)

    with qtbot.waitSignal(demo_controller.jobsUpdated, timeout=5000):
        view.scope_combo.setCurrentIndex(1)

    session = demo_controller.session("demo")
    assert session.queue_scope == "all"
    assert "Cluster scope enabled" in view.mode_hint.text()
