"""Tests for the history retention/prune policy."""

from datetime import timedelta

from slurmhub.db.engine import Database, _run_migrations, make_engine
from slurmhub.db.models import Job, UsageSnapshot, utcnow
from slurmhub.db.repository import Repository
from slurmhub.squeue_parser import SlurmJob


def fresh_db() -> Database:
    engine = make_engine("sqlite://", in_memory=True)
    _run_migrations(engine)
    return Database(engine)


def _seed_old_running_job(db, repo, job_id, days_old) -> int:
    """Insert a job + one snapshot, backdated ``days_old`` days."""
    with db.session() as s:
        job = SlurmJob(
            job_id=job_id, name="j", state="RUNNING", time="01:00:00",
            submit_time=f"2026-01-0{1}T00:00:00",
        )
        pk = repo.upsert_job(s, "p", job)
        repo.record_snapshot(s, pk, job, utcnow())
        row = s.get(Job, pk)
        row.last_seen = utcnow() - timedelta(days=days_old)
        s.commit()
        return pk


class TestRetention:
    def test_prune_removes_old_non_favourite_and_snapshots(self):
        db = fresh_db()
        repo = Repository()
        _seed_old_running_job(db, repo, "1", days_old=60)
        with db.session() as s:
            removed = repo.prune(s, retention_days=30, now=utcnow())
            assert removed == 1
            assert len(repo.query_runs(s)) == 0
            assert s.query(UsageSnapshot).count() == 0  # cascaded
        db.close()

    def test_prune_keeps_recent_job(self):
        db = fresh_db()
        repo = Repository()
        _seed_old_running_job(db, repo, "1", days_old=5)
        with db.session() as s:
            removed = repo.prune(s, retention_days=30, now=utcnow())
            assert removed == 0
            assert len(repo.query_runs(s)) == 1
        db.close()

    def test_prune_exempts_favourites(self):
        db = fresh_db()
        repo = Repository()
        pk = _seed_old_running_job(db, repo, "1", days_old=90)
        with db.session() as s:
            repo.set_favourite(s, pk, True, note="keep me")
        with db.session() as s:
            removed = repo.prune(s, retention_days=30, now=utcnow())
            assert removed == 0
            runs = repo.query_runs(s)
            assert len(runs) == 1
            assert runs[0].favourite is True
        db.close()

    def test_prune_zero_is_noop(self):
        db = fresh_db()
        repo = Repository()
        _seed_old_running_job(db, repo, "1", days_old=999)
        with db.session() as s:
            assert repo.prune(s, retention_days=0, now=utcnow()) == 0
            assert len(repo.query_runs(s)) == 1
        db.close()
