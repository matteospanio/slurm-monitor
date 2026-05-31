"""Tests for resource-usage aggregates computed from the jobs table."""

from datetime import timedelta

from slurmhub.db.engine import Database, _run_migrations, make_engine
from slurmhub.db.models import Job, utcnow
from slurmhub.db.repository import Repository
from slurmhub.squeue_parser import SlurmJob


def fresh_db() -> Database:
    engine = make_engine("sqlite://", in_memory=True)
    _run_migrations(engine)
    return Database(engine)


def _add(s, repo, profile, jid, *, gres=None, cpus=None, mem=None, time="01:00:00"):
    job = SlurmJob(
        job_id=jid, name="j", state="COMPLETED", time=time,
        submit_time=f"2026-01-01T00:00:0{jid[-1]}",
        gres=gres, num_cpus=cpus, mem_requested_mb=mem,
    )
    return repo.upsert_job(s, profile, job)


class TestAggregates:
    def test_resource_hours_match_hand_calc(self):
        db = fresh_db()
        repo = Repository()
        with db.session() as s:
            # 2 GPUs, 4 CPUs, 8192MB, for 2 hours.
            _add(s, repo, "p", "1", gres="gpu:l40s:2", cpus=4, mem=8192,
                 time="02:00:00")
            s.commit()
        with db.session() as s:
            tot = repo.aggregate_usage(s)
            assert tot.job_count == 1
            assert tot.gpu_hours == 4.0  # 2 gpu * 2h
            assert tot.cpu_hours == 8.0  # 4 cpu * 2h
            assert tot.mem_gb_hours == 16.0  # 8GB * 2h
        db.close()

    def test_per_profile_breakdown(self):
        db = fresh_db()
        repo = Repository()
        with db.session() as s:
            _add(s, repo, "a", "1", gres="gpu:l40s:1", cpus=2, time="01:00:00")
            _add(s, repo, "b", "2", gres="gpu:a100:4", cpus=8, time="01:00:00")
            s.commit()
        with db.session() as s:
            tot = repo.aggregate_usage(s)  # profile=None → per-profile
            assert tot.job_count == 2
            assert {p.profile_name for p in tot.per_profile} == {"a", "b"}
            a = next(p for p in tot.per_profile if p.profile_name == "a")
            assert a.gpu_hours == 1.0
        db.close()

    def test_scope_to_single_profile(self):
        db = fresh_db()
        repo = Repository()
        with db.session() as s:
            _add(s, repo, "a", "1", gres="gpu:l40s:1", time="01:00:00")
            _add(s, repo, "b", "2", gres="gpu:a100:4", time="01:00:00")
            s.commit()
        with db.session() as s:
            tot = repo.aggregate_usage(s, profile="b")
            assert tot.job_count == 1
            assert tot.gpu_hours == 4.0
            assert tot.per_profile == []
        db.close()

    def test_date_range_excludes_old(self):
        db = fresh_db()
        repo = Repository()
        with db.session() as s:
            pk = _add(s, repo, "p", "1", gres="gpu:l40s:1", time="01:00:00")
            s.get(Job, pk).last_seen = utcnow() - timedelta(days=40)
            s.commit()
        with db.session() as s:
            recent = repo.aggregate_usage(s, since=utcnow() - timedelta(days=7))
            assert recent.job_count == 0
            assert recent.gpu_hours == 0.0
        db.close()

    def test_avg_gpu_util_from_snapshots(self):
        db = fresh_db()
        repo = Repository()
        from slurmhub.scontrol_parser import GpuInfo, JobDetails

        details = JobDetails(
            num_gpus=2,
            gpu_type="l40s",
            gpus=[GpuInfo(utilization=80), GpuInfo(utilization=90)],
        )
        with db.session() as s:
            job = SlurmJob(
                job_id="1", name="j", state="RUNNING", time="01:00:00",
                submit_time="2026-01-01T00:00:00", gres="gpu:l40s:2",
            )
            pk = repo.upsert_job(s, "p", job, details)
            repo.record_snapshot(s, pk, job, utcnow(), details)
            s.commit()
        with db.session() as s:
            tot = repo.aggregate_usage(s)
            assert tot.avg_gpu_util == 85.0
        db.close()
