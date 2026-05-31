"""Tests for the Qt GUI controller: filtering logic and the worker pipeline."""

from contextlib import contextmanager
from unittest.mock import MagicMock

from slurmhub.config import ProfileConfig
from slurmhub.db.models import UsageSnapshot
from slurmhub.gui.controller import (
    ProfileSession,
    fetch_profile_data,
    get_filtered_jobs,
)
from slurmhub.slurm.squeue import SlurmJob


def _job(job_id: str, name: str, state: str, time: str = "00:01") -> SlurmJob:
    return SlurmJob(job_id=job_id, name=name, state=state, time=time)


def test_get_filtered_jobs_state_name_and_sort():
    session = ProfileSession(ProfileConfig(name="demo"), demo=True)
    session.jobs = [
        _job("3", "alpha", "RUNNING", "00:10"),
        _job("2", "beta", "PENDING", "00:05"),
        _job("1", "alphagamma", "RUNNING", "01:00"),
    ]

    session.state_filter = "RUNNING"
    assert {j.job_id for j in get_filtered_jobs(session)} == {"3", "1"}

    session.state_filter = "ALL"
    session.name_filter = "alpha"
    assert {j.job_id for j in get_filtered_jobs(session)} == {"3", "1"}

    session.name_filter = ""
    session.sort_mode = "name"
    assert [j.name for j in get_filtered_jobs(session)] == [
        "alpha",
        "alphagamma",
        "beta",
    ]


def test_name_filter_matches_job_id():
    session = ProfileSession(ProfileConfig(name="demo"), demo=True)
    session.jobs = [_job("2172044", "train", "RUNNING"), _job("9", "eval", "RUNNING")]
    session.name_filter = "2172"
    assert [j.job_id for j in get_filtered_jobs(session)] == ["2172044"]


def test_refresh_populates_jobs_off_thread(demo_controller, qtbot):
    with qtbot.waitSignal(demo_controller.jobsUpdated, timeout=5000):
        demo_controller.refresh_profile("demo")

    session = demo_controller.session("demo")
    assert len(session.jobs) > 0
    assert session.error_message is None
    assert session.last_updated
    # Demo cluster capacity / queue stats also arrive on the first cycle.
    assert session.cluster_capacity is not None
    assert session.queue_stats is not None


def test_cancel_job_emits_success(demo_controller, qtbot):
    with qtbot.waitSignal(demo_controller.jobActionFinished, timeout=5000) as blocker:
        demo_controller.cancel_job("demo", "2172044")
    profile, job_id, verb, ok, _msg = blocker.args
    assert profile == "demo"
    assert job_id == "2172044"
    assert verb == "cancel"
    assert ok is True


def test_start_schedules_utilization_timers_when_enabled(demo_controller):
    demo_controller.start()
    assert "demo" in demo_controller._util_timers


def test_capture_utilization_records_measured_values(demo_controller, qtbot):
    with qtbot.waitSignal(demo_controller.jobsUpdated, timeout=5000):
        demo_controller.refresh_profile("demo")

    session = demo_controller.session("demo")
    demo_controller._capture_utilization_work(session, "demo")

    with demo_controller.database.session() as db_session:
        measured = (
            db_session.query(UsageSnapshot)
            .filter(UsageSnapshot.gpu_util_avg.isnot(None))
            .all()
        )
    assert measured


def test_action_is_queued_while_refresh_running(demo_controller):
    session = demo_controller.session("demo")
    session.refresh_in_progress = True

    demo_controller.cancel_job("demo", "2172044")

    assert session.pending_actions == [("2172044", "scancel 2172044", "cancel")]


def test_refresh_is_deferred_while_action_running(demo_controller):
    session = demo_controller.session("demo")
    session.action_in_progress = True

    demo_controller.refresh_profile("demo")

    assert session.pending_refresh is True
    assert session.refresh_in_progress is False


def test_pending_refresh_replayed_after_action_result(demo_controller, monkeypatch):
    session = demo_controller.session("demo")
    session.action_in_progress = True
    session.pending_refresh = True
    calls = []

    monkeypatch.setattr(
        demo_controller,
        "refresh_profile",
        lambda name: calls.append(name),
    )

    demo_controller._on_action_result(("demo", "1", "cancel", False, ""))

    assert calls == ["demo"]
    assert session.pending_refresh is False


def test_cluster_scope_capture_persists_only_my_jobs(monkeypatch):
    class _DummyDatabase:
        @contextmanager
        def session(self):
            yield object()

    session = ProfileSession(ProfileConfig(name="demo"), demo=True)
    session.queue_scope = "all"

    my_active = _job("101", "mine-active", "RUNNING")
    other_active = _job("999", "other-active", "RUNNING")
    my_history = _job("42", "mine-done", "COMPLETED", "10:00")

    squeue_calls = []

    def fake_fetch_squeue_jobs(*_args, include_all=False, **_kwargs):
        squeue_calls.append(include_all)
        return [my_active, other_active] if include_all else [my_active]

    monkeypatch.setattr(
        "slurmhub.gui.controller.fetch_squeue_jobs", fake_fetch_squeue_jobs
    )
    monkeypatch.setattr(
        "slurmhub.gui.controller.fetch_sacct_jobs",
        lambda *_args, **_kwargs: [my_history],
    )
    monkeypatch.setattr(
        "slurmhub.gui.controller.fetch_sinfo", lambda *_args, **_kwargs: (None, [], [])
    )
    monkeypatch.setattr(
        "slurmhub.gui.controller.fetch_cluster_queue_stats",
        lambda *_args, **_kwargs: None,
    )

    repository = MagicMock()
    result = fetch_profile_data(session, "demo", _DummyDatabase(), repository)

    assert {job.job_id for job in result.jobs} == {"101", "999"}
    persisted_jobs = repository.capture_refresh.call_args[0][2]
    assert {job.job_id for job in persisted_jobs} == {"42", "101"}
    assert squeue_calls[:2] == [True, False]
