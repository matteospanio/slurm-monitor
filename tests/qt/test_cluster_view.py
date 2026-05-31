"""Tests for the Cluster Status view: capacity bars + partition/node tables."""

from slurmhub.qt.views.cluster_view import ClusterView


def test_cluster_view_populates_from_demo(demo_controller, qtbot):
    view = ClusterView(demo_controller)
    qtbot.addWidget(view)

    with qtbot.waitSignal(demo_controller.jobsUpdated, timeout=5000):
        demo_controller.refresh_profile("demo")
    view.reload()

    assert view.partitions_model.rowCount() > 0
    assert view.nodes_model.rowCount() > 0
    assert "up" in view.nodes_summary.text()

    session = demo_controller.session("demo")
    cap = session.cluster_capacity
    assert cap is not None
    # CPU bar reflects the capacity percentage.
    assert view.cpu_bar._percentage == cap.cpu_percentage


def test_cluster_view_handles_missing_capacity(demo_controller, qtbot):
    # Before any fetch, capacity is None and the view degrades gracefully.
    view = ClusterView(demo_controller)
    qtbot.addWidget(view)
    assert view.partitions_model.rowCount() == 0
    assert "Waiting" in view.nodes_summary.text()
