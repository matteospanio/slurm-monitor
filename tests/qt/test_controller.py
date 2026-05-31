"""Tests for the Qt GUI controller: filtering logic and the worker pipeline."""

from slurmhub.config import ProfileConfig
from slurmhub.qt.controller import ProfileSession, get_filtered_jobs
from slurmhub.squeue_parser import SlurmJob


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
