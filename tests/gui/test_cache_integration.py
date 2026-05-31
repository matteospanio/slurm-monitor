"""Tests for the controller's startup snapshot-cache behaviour."""

from slurmhub.core.snapshot_cache import CachedSnapshot, SnapshotCache
from slurmhub.slurm.squeue import SlurmJob


def test_live_refresh_saves_snapshot(demo_controller, qtbot, tmp_path):
    demo_controller._cache = SnapshotCache(tmp_path)
    with qtbot.waitSignal(demo_controller.jobsUpdated, timeout=5000):
        demo_controller.refresh_profile("demo")

    assert demo_controller._cache.path("demo").exists()
    snap = demo_controller._cache.load("demo")
    assert snap is not None and len(snap.jobs) > 0
    # A live refresh is not "cached".
    assert demo_controller.session("demo").is_cached is False


def test_cached_snapshot_shown_then_cleared(demo_controller, qtbot, tmp_path):
    cache = SnapshotCache(tmp_path)
    cache.save(
        CachedSnapshot(
            profile_name="demo",
            cached_at="2026-01-01 00:00:00",
            jobs=[SlurmJob(job_id="1", name="x", state="RUNNING", time="00:01")],
        )
    )
    demo_controller._cache = cache

    # Loading the cache paints data immediately and marks it cached.
    with qtbot.waitSignal(demo_controller.jobsUpdated, timeout=2000):
        demo_controller._load_cached_snapshots()
    session = demo_controller.session("demo")
    assert session.is_cached is True
    assert len(session.jobs) == 1
    assert session.last_updated == "2026-01-01 00:00:00"

    # A live refresh replaces the cached view and clears the flag.
    with qtbot.waitSignal(demo_controller.jobsUpdated, timeout=5000):
        demo_controller.refresh_profile("demo")
    assert demo_controller.session("demo").is_cached is False


def test_actions_refused_while_cached(demo_controller, qtbot, tmp_path):
    session = demo_controller.session("demo")
    session.is_cached = True

    with qtbot.waitSignal(demo_controller.jobActionFinished, timeout=2000) as blocker:
        demo_controller.cancel_job("demo", "1")
    _profile, _job_id, verb, ok, message = blocker.args
    assert verb == "cancel"
    assert ok is False
    assert "live" in message.lower()
