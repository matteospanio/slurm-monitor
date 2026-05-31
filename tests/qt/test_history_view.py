"""Tests for the History view: querying, favourites/notes, and analytics."""

from slurmhub.qt.views.history_view import HistoryView, _fmt_elapsed, _fmt_gpu


def _wait_loaded(view, qtbot):
    # HistoryView.reload() runs in __init__; wait for that single async load.
    qtbot.waitUntil(
        lambda: view.model.rowCount() > 0 or "run" in view.status.text(),
        timeout=5000,
    )


def test_fmt_helpers():
    assert _fmt_elapsed(None) == ""
    assert _fmt_elapsed(0) == "0:00"
    assert _fmt_elapsed(90) == "1:30"
    assert _fmt_elapsed(3661) == "1:01:01"


def test_history_populates_from_demo_db(demo_controller, qtbot):
    view = HistoryView(demo_controller)
    qtbot.addWidget(view)
    _wait_loaded(view, qtbot)
    assert view.model.rowCount() > 0
    assert "run" in view.status.text()
    assert "GPU-hours" in view.usage_summary.text()
    assert len(view.chart.series()) == 1


def test_state_filter_restricts_to_completed(demo_controller, qtbot):
    view = HistoryView(demo_controller)
    qtbot.addWidget(view)
    _wait_loaded(view, qtbot)

    # "Completed" is index 3 in _STATE_FILTERS. After the async reload lands,
    # every row must be COMPLETED (server-side filtered by query_runs).
    view.state_combo.setCurrentIndex(3)
    qtbot.waitUntil(
        lambda: all(
            view.model.row_at(r).state == "COMPLETED"
            for r in range(view.model.rowCount())
        )
        and "run" in view.status.text(),
        timeout=5000,
    )
    assert all(
        view.model.row_at(r).state == "COMPLETED"
        for r in range(view.model.rowCount())
    )


def test_toggle_favourite_persists(demo_controller, qtbot):
    view = HistoryView(demo_controller)
    qtbot.addWidget(view)
    _wait_loaded(view, qtbot)

    view.table.selectRow(0)
    run = view.selected_run()
    assert run is not None
    before = run.favourite

    view._toggle_favourite()
    qtbot.waitUntil(
        lambda: any(
            r is not None and r.job_id == run.job_id and r.favourite != before
            for r in (view.model.row_at(i) for i in range(view.model.rowCount()))
        ),
        timeout=5000,
    )


def test_history_disabled_without_database(qtbot):
    from slurmhub.config import AppConfig, ProfileConfig
    from slurmhub.qt.controller import AppController

    controller = AppController(
        AppConfig(profiles={"x": ProfileConfig(name="x")}), demo=False, database=None
    )
    view = HistoryView(controller)
    qtbot.addWidget(view)
    assert "disabled" in view.status.text().lower()
    controller.shutdown()
