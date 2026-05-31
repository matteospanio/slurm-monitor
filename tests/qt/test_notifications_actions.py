"""Tests for Phase 6: completion notifications + extra job actions."""

from slurmhub.config import AppConfig, ProfileConfig, SSHConfig
from slurmhub.demo_data import DEMO_HOST
from slurmhub.db import open_demo_database
from slurmhub.qt.controller import AppController, ProfileSession
from slurmhub.squeue_parser import SlurmJob


def _job(job_id, state):
    return SlurmJob(job_id=job_id, name=f"job{job_id}", state=state, time="00:01")


def test_jobs_finished_emitted_on_terminal_transition(qtbot):
    cfg = AppConfig(profiles={"p": ProfileConfig(name="p", ssh=SSHConfig(host="h"))})
    controller = AppController(cfg, demo=False)
    session = controller.session("p")

    # Seed a "previous" refresh where job 1 was RUNNING.
    session._prev_states = {"1": "RUNNING", "2": "RUNNING"}
    session._states_seen = True

    from slurmhub.qt.controller import FetchResult

    result = FetchResult(profile_name="p", jobs=[_job("1", "COMPLETED"), _job("2", "RUNNING")])
    with qtbot.waitSignal(controller.jobsFinished, timeout=2000) as blocker:
        controller._on_fetch_finished(result)
    name, transitions = blocker.args
    assert name == "p"
    assert transitions == [("1", "job1", "COMPLETED")]
    controller.shutdown()


def test_no_notification_on_first_refresh(qtbot):
    cfg = AppConfig(profiles={"p": ProfileConfig(name="p", ssh=SSHConfig(host="h"))})
    controller = AppController(cfg, demo=False)

    from slurmhub.qt.controller import FetchResult

    result = FetchResult(profile_name="p", jobs=[_job("1", "COMPLETED")])
    # First-ever refresh: _states_seen is False, so no completion is reported.
    with qtbot.assertNotEmitted(controller.jobsFinished):
        controller._on_fetch_finished(result)
    controller.shutdown()


def test_requeue_action_emits_finished(demo_controller, qtbot):
    with qtbot.waitSignal(demo_controller.jobActionFinished, timeout=5000) as blocker:
        demo_controller.requeue_job("demo", "421578")
    _profile, _job_id, verb, ok, _msg = blocker.args
    assert verb == "requeue" and ok is True


def test_hold_and_release_actions(demo_controller, qtbot):
    with qtbot.waitSignal(demo_controller.jobActionFinished, timeout=5000) as b1:
        demo_controller.hold_job("demo", "421578")
    assert b1.args[2] == "hold" and b1.args[3] is True

    with qtbot.waitSignal(demo_controller.jobActionFinished, timeout=5000) as b2:
        demo_controller.release_job("demo", "421578")
    assert b2.args[2] == "release" and b2.args[3] is True
