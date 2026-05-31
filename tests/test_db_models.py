"""Tests for the history DB models + repository write/identity semantics."""

import pytest

from slurmhub.db.engine import Database, _run_migrations, make_engine
from slurmhub.db.models import Job, UsageSnapshot
from slurmhub.db.repository import Repository
from slurmhub.slurm.squeue import SlurmJob


def fresh_db() -> Database:
    engine = make_engine("sqlite://", in_memory=True)
    _run_migrations(engine)
    return Database(engine)


def _job(jid, state="RUNNING", submit=None, name="job", time="00:10:00", **kw):
    return SlurmJob(
        job_id=jid,
        name=name,
        state=state,
        time=time,
        submit_time=submit,
        gres=kw.get("gres"),
        num_cpus=kw.get("num_cpus"),
        mem_requested_mb=kw.get("mem"),
    )


class TestUpsertIdentity:
    def test_same_natural_key_dedups(self):
        db = fresh_db()
        repo = Repository()
        with db.session() as s:
            pk1 = repo.upsert_job(s, "p", _job("100", submit="2026-01-01T00:00:00"))
            s.commit()
            pk2 = repo.upsert_job(
                s, "p", _job("100", submit="2026-01-01T00:00:00", state="COMPLETED")
            )
            s.commit()
            assert pk1 == pk2
            runs = repo.query_runs(s)
            assert len(runs) == 1
            assert runs[0].state == "COMPLETED"
        db.close()

    def test_reused_job_id_distinct_submit_two_rows(self):
        db = fresh_db()
        repo = Repository()
        with db.session() as s:
            repo.upsert_job(s, "p", _job("7", submit="2026-01-01T00:00:00"))
            repo.upsert_job(s, "p", _job("7", submit="2026-03-01T00:00:00"))
            s.commit()
            assert len(repo.query_runs(s)) == 2
        db.close()

    def test_merge_on_empty_submit(self):
        db = fresh_db()
        repo = Repository()
        with db.session() as s:
            pk1 = repo.upsert_job(s, "p", _job("9", submit=None))  # "" placeholder
            s.commit()
            pk2 = repo.upsert_job(s, "p", _job("9", submit="2026-02-02T00:00:00"))
            s.commit()
            assert pk1 == pk2  # merged into the placeholder row
            runs = repo.query_runs(s)
            assert len(runs) == 1
            assert runs[0].submit_time == "2026-02-02T00:00:00"
        db.close()

    def test_profile_tagging_keeps_runs_separate(self):
        db = fresh_db()
        repo = Repository()
        with db.session() as s:
            repo.upsert_job(s, "alpha", _job("5", submit="2026-01-01T00:00:00"))
            repo.upsert_job(s, "beta", _job("5", submit="2026-01-01T00:00:00"))
            s.commit()
            runs = repo.query_runs(s)
            assert {r.profile_name for r in runs} == {"alpha", "beta"}
            assert len(repo.query_runs(s, profile="alpha")) == 1
        db.close()

    def test_gres_and_resource_fields_parsed(self):
        db = fresh_db()
        repo = Repository()
        with db.session() as s:
            repo.upsert_job(
                s,
                "p",
                _job("1", submit="2026-01-01T00:00:00", gres="gpu:a100:4",
                     num_cpus=8, mem=65536),
            )
            s.commit()
            run = repo.query_runs(s)[0]
            assert run.gpu_count == 4
            assert run.gpu_type == "a100"
            assert run.num_cpus == 8
            assert run.mem_requested_mb == 65536
        db.close()


class TestSnapshots:
    def test_capture_snapshots_active_only(self):
        db = fresh_db()
        repo = Repository()
        from slurmhub.db.models import utcnow

        jobs = [
            _job("1", state="RUNNING", submit="2026-01-01T00:00:00"),
            _job("2", state="COMPLETED", submit="2026-01-01T00:00:00"),
            _job("3", state="PENDING", submit="2026-01-01T00:00:00"),
        ]
        with db.session() as s:
            repo.capture_refresh(s, "p", jobs, utcnow())
        with db.session() as s:
            # All three runs recorded...
            assert len(repo.query_runs(s)) == 3
            # ...but only the RUNNING one accrued a snapshot.
            assert s.query(UsageSnapshot).count() == 1
        db.close()

    def test_terminal_job_does_not_accrue_snapshots_across_cycles(self):
        db = fresh_db()
        repo = Repository()
        from slurmhub.db.models import utcnow

        done = [_job("42", state="COMPLETED", submit="2026-01-01T00:00:00")]
        with db.session() as s:
            repo.capture_refresh(s, "p", done, utcnow())
        with db.session() as s:
            repo.capture_refresh(s, "p", done, utcnow())
        with db.session() as s:
            assert s.query(UsageSnapshot).count() == 0
        db.close()
