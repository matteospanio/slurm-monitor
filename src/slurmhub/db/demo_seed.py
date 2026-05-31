"""Seed data for the ``--demo`` in-memory history database.

Populates a believable history (completed/failed/cancelled runs plus the
currently-running demo jobs), a couple of favourites, and time-series snapshots
with measured utilization, so the history and analytics screens are
demonstrable without a live cluster. Never touches ``~/.config``.
"""

from __future__ import annotations

from datetime import timedelta

from slurmhub.db.engine import Database
from slurmhub.db.models import Favourite, Job, UsageSnapshot, utcnow

_PROFILE = "demo"


def _job(seen_days_ago: float, **fields) -> tuple[Job, float]:
    """Build a Job row whose first/last-seen sit ``seen_days_ago`` in the past."""
    now = utcnow()
    seen = now - timedelta(days=seen_days_ago)
    fields.setdefault("first_seen", seen - timedelta(hours=1))
    fields.setdefault("last_seen", seen)
    return Job(profile_name=_PROFILE, **fields), seen_days_ago


def seed_demo_database(db: Database) -> None:
    """Insert sample runs, favourites, and snapshots into ``db``."""
    runs: list[Job] = [
        Job(
            profile_name=_PROFILE,
            job_id="420918",
            submit_time="2026-05-19T21:40:00",
            name="train_bert_large",
            state="COMPLETED",
            gres="gpu:a100:8",
            gpu_count=8,
            gpu_type="a100",
            num_cpus=32,
            mem_requested_mb=524288,
            partition="gpu",
            elapsed_seconds=115200,
            start_time="2026-05-19T21:42:10",
            end_time="2026-05-21T05:42:10",
            stdout_path="/home/demo-user/projects/bert/logs/420918.out",
            first_seen=utcnow() - timedelta(days=12, hours=8),
            last_seen=utcnow() - timedelta(days=11),
        ),
        Job(
            profile_name=_PROFILE,
            job_id="421044",
            submit_time="2026-05-22T06:05:00",
            name="sweep_lr",
            state="COMPLETED",
            gres="gpu:l40s:1",
            gpu_count=1,
            gpu_type="l40s",
            num_cpus=4,
            mem_requested_mb=24576,
            partition="gpu",
            elapsed_seconds=9000,
            stdout_path="/home/demo-user/projects/hpo/logs/421044.out",
            first_seen=utcnow() - timedelta(days=9, hours=2),
            last_seen=utcnow() - timedelta(days=9),
        ),
        Job(
            profile_name=_PROFILE,
            job_id="421421",
            submit_time="2026-05-22T07:01:00",
            name="train_resnet50",
            state="COMPLETED",
            gres="gpu:l40s:4",
            gpu_count=4,
            gpu_type="l40s",
            num_cpus=16,
            mem_requested_mb=131072,
            partition="gpu",
            elapsed_seconds=22364,
            stdout_path="/home/demo-user/projects/vision-models/logs/421421.out",
            first_seen=utcnow() - timedelta(days=7, hours=6),
            last_seen=utcnow() - timedelta(days=7),
        ),
        Job(
            profile_name=_PROFILE,
            job_id="421502",
            submit_time="2026-05-23T11:20:00",
            name="eval_transformer",
            state="COMPLETED",
            gres="gpu:a100:2",
            gpu_count=2,
            gpu_type="a100",
            num_cpus=8,
            mem_requested_mb=65536,
            partition="gpu",
            elapsed_seconds=6918,
            first_seen=utcnow() - timedelta(days=6, hours=2),
            last_seen=utcnow() - timedelta(days=6),
        ),
        Job(
            profile_name=_PROFILE,
            job_id="421561",
            submit_time="2026-05-24T09:15:00",
            name="cuda_smoke_test",
            state="FAILED",
            gres="gpu:l40s:1",
            gpu_count=1,
            gpu_type="l40s",
            num_cpus=4,
            mem_requested_mb=24576,
            partition="gpu",
            elapsed_seconds=34,
            first_seen=utcnow() - timedelta(days=5, hours=1),
            last_seen=utcnow() - timedelta(days=5),
        ),
        Job(
            profile_name=_PROFILE,
            job_id="421577",
            submit_time="2026-05-25T14:02:00",
            name="preprocess_data",
            state="CANCELLED",
            num_cpus=32,
            mem_requested_mb=98304,
            partition="cpu",
            elapsed_seconds=491,
            first_seen=utcnow() - timedelta(days=4, hours=3),
            last_seen=utcnow() - timedelta(days=4),
        ),
        # Currently running jobs — mirror the live demo squeue fixtures.
        Job(
            profile_name=_PROFILE,
            job_id="421578",
            submit_time="2026-05-21T03:08:11",
            name="train_resnet50",
            state="RUNNING",
            gres="gpu:l40s:4",
            gpu_count=4,
            gpu_type="l40s",
            num_cpus=16,
            mem_requested_mb=131072,
            partition="gpu",
            node_list="node-gpu-04",
            elapsed_seconds=102731,
            start_time="2026-05-21T03:09:42",
            stdout_path="/home/demo-user/projects/vision-models/logs/421578.out",
            stderr_path="/home/demo-user/projects/vision-models/logs/421578.err",
            first_seen=utcnow() - timedelta(days=1, hours=4),
            last_seen=utcnow(),
        ),
        Job(
            profile_name=_PROFILE,
            job_id="421579",
            submit_time="2026-05-22T04:55:33",
            name="eval_transformer",
            state="RUNNING",
            gres="gpu:a100:2",
            gpu_count=2,
            gpu_type="a100",
            num_cpus=8,
            mem_requested_mb=65536,
            partition="gpu",
            node_list="node-gpu-02",
            elapsed_seconds=11662,
            start_time="2026-05-22T04:56:14",
            stdout_path="/home/demo-user/projects/nlp-bench/logs/421579.out",
            first_seen=utcnow() - timedelta(hours=3, minutes=20),
            last_seen=utcnow(),
        ),
    ]

    with db.session() as session:
        session.add_all(runs)
        session.flush()

        by_id = {j.job_id: j for j in runs}

        # Time-series snapshots with measured utilization for the GPU jobs.
        now = utcnow()
        for job_id, util, mem_used in (
            ("421578", [88, 91, 94, 90, 92, 89], 41024),
            ("421579", [74, 76, 71, 78, 73], 52214),
        ):
            job = by_id[job_id]
            n = len(util)
            for i, u in enumerate(util):
                session.add(
                    UsageSnapshot(
                        job_pk=job.id,
                        captured_at=now - timedelta(minutes=5 * (n - i)),
                        state="RUNNING",
                        elapsed_seconds=job.elapsed_seconds - 300 * (n - i),
                        gpu_count=job.gpu_count,
                        num_cpus=job.num_cpus,
                        mem_requested_mb=job.mem_requested_mb,
                        gpu_util_avg=u,
                        mem_used_mb=mem_used,
                    )
                )

        # Favourites: one with a note, one plain.
        session.add(
            Favourite(job_pk=by_id["421421"].id, note="baseline run — keep")
        )
        session.add(Favourite(job_pk=by_id["421578"].id, note=""))
        session.commit()
