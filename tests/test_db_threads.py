"""Concurrency test: a writer and a reader on separate threads must coexist.

Exercises the WAL + busy_timeout + per-operation-session design against a real
file database (in-memory DBs don't reproduce file locking).
"""

import threading

from slurmhub.config import DatabaseConfig
from slurmhub.db.engine import open_database
from slurmhub.db.models import utcnow
from slurmhub.db.repository import Repository
from slurmhub.slurm.squeue import SlurmJob


def test_concurrent_write_and_read_no_lock_errors(tmp_path):
    cfg = DatabaseConfig(enabled=True, path=str(tmp_path / "jobs.db"))
    db = open_database(cfg)
    assert db is not None
    repo = Repository()
    errors: list[Exception] = []
    stop = threading.Event()

    def writer():
        try:
            for i in range(40):
                job = SlurmJob(
                    job_id=str(i % 5),
                    name="w",
                    state="RUNNING",
                    time="00:05:00",
                    submit_time="2026-01-01T00:00:00",
                )
                with db.session() as s:
                    repo.capture_refresh(s, "p", [job], utcnow())
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            stop.set()

    def reader():
        try:
            while not stop.is_set():
                with db.session() as s:
                    repo.query_runs(s, limit=50)
                    repo.aggregate_usage(s)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    tw, tr = threading.Thread(target=writer), threading.Thread(target=reader)
    tr.start()
    tw.start()
    tw.join(timeout=30)
    tr.join(timeout=5)
    db.close()

    assert not errors, f"thread errors: {errors}"
