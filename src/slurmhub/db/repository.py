"""Data-access layer for the job-history database.

All public methods take an explicit :class:`~sqlalchemy.orm.Session` (one per
operation, opened by the caller via ``with db.session() as s:``) and return
plain detached dataclasses — never live ORM instances — so results can cross
the Textual worker-thread boundary without ``DetachedInstanceError``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from slurmhub.db.models import Favourite, Job, UsageSnapshot, utcnow
from slurmhub.slurm.scontrol import JobDetails, parse_mem_bytes
from slurmhub.slurm.squeue import SlurmJob, mem_str_to_mb
from slurmhub.slurm.util import time_to_seconds

# States that no longer consume cluster resources — recorded in history but
# never snapshotted again (so the time-series table stays bounded).
TERMINAL_STATES = {
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "TIMEOUT",
    "OUT_OF_MEMORY",
    "NODE_FAIL",
    "BOOT_FAIL",
    "DEADLINE",
    "PREEMPTED",
}
# States during which a job is actually consuming resources — the only ones we
# append usage snapshots for.
SNAPSHOT_STATES = {"RUNNING", "COMPLETING", "CONFIGURING", "RESIZING"}

_ZERO_TIME_STRINGS = {"0:00", "00:00", "0:00:00", "00:00:00"}


def _elapsed_seconds(time_str: Optional[str]) -> Optional[int]:
    """Parse a Slurm elapsed string, distinguishing a real 0 from a parse fail."""
    if not time_str:
        return None
    secs = time_to_seconds(time_str)
    if secs == 0 and time_str.strip() not in _ZERO_TIME_STRINGS:
        return None
    return secs


def _parse_gres(gres: Optional[str]) -> tuple[Optional[int], Optional[str]]:
    """Derive (gpu_count, gpu_type) from a Slurm gres string."""
    if not gres or gres == "(null)":
        return None, None
    for part in gres.split(","):
        part = part.strip()
        if part.startswith("gpu:"):
            segs = part.split(":")
            if len(segs) == 3 and segs[2].isdigit():
                return int(segs[2]), segs[1]
            if len(segs) == 2 and segs[1].isdigit():
                return int(segs[1]), None
    return None, None


@dataclass
class JobRun:
    """Detached view of a run for the history and detail screens."""

    pk: int
    profile_name: str
    job_id: str
    name: str
    state: str
    submit_time: str
    start_time: Optional[str]
    end_time: Optional[str]
    elapsed_seconds: Optional[int]
    num_cpus: Optional[int]
    gpu_count: Optional[int]
    gpu_type: Optional[str]
    mem_requested_mb: Optional[int]
    partition: Optional[str]
    work_dir: Optional[str]
    stdout_path: Optional[str]
    stderr_path: Optional[str]
    favourite: bool
    note: Optional[str]
    last_seen: datetime


@dataclass
class UsageTotals:
    """Aggregated resource consumption over a time range."""

    profile_name: Optional[str]
    gpu_hours: float
    cpu_hours: float
    mem_gb_hours: float
    avg_gpu_util: Optional[float]
    job_count: int
    per_profile: list["UsageTotals"] = field(default_factory=list)


@dataclass
class SnapshotSummary:
    """Summary stats computed from a run's usage snapshots."""

    snapshot_count: int = 0
    first_captured_at: Optional[datetime] = None
    last_captured_at: Optional[datetime] = None
    latest_cpu_util: Optional[int] = None
    avg_cpu_util: Optional[float] = None
    peak_cpu_util: Optional[int] = None
    latest_gpu_util: Optional[int] = None
    avg_gpu_util: Optional[float] = None
    peak_gpu_util: Optional[int] = None
    latest_mem_used_mb: Optional[int] = None
    peak_mem_used_mb: Optional[int] = None


@dataclass
class SnapshotPoint:
    """One persisted usage point for a run's time series."""

    captured_at: datetime
    state: Optional[str]
    elapsed_seconds: Optional[int]
    num_cpus: Optional[int]
    gpu_count: Optional[int]
    cpu_util_avg: Optional[int]
    gpu_util_avg: Optional[int]
    mem_requested_mb: Optional[int]
    mem_used_mb: Optional[int]


class Repository:
    """CRUD + query surface over the history tables."""

    # ── writes (refresh / utilization workers) ───────────────────────────

    def capture_refresh(
        self,
        session: Session,
        profile_name: str,
        jobs: list[SlurmJob],
        captured_at: datetime,
    ) -> None:
        """Upsert every job and append snapshots for active/final states.

        Running-like states are snapshotted each cycle. Terminal states get one
        final snapshot (at most once) so completed jobs retain inspectable
        CPU/GPU/memory history even after they leave the queue.
        """
        for job in jobs:
            pk = self.upsert_job(session, profile_name, job)
            if job.state in SNAPSHOT_STATES:
                self.record_snapshot(session, pk, job, captured_at)
            elif job.state in TERMINAL_STATES:
                self._record_terminal_snapshot_once(session, pk, job, captured_at)
        session.commit()

    def upsert_job(
        self,
        session: Session,
        profile_name: str,
        job: SlurmJob,
        details: Optional[JobDetails] = None,
    ) -> int:
        """Insert or update the run row, returning its surrogate primary key.

        Merges a real ``submit_time`` into an earlier ``""`` placeholder row in
        place so the surrogate PK (and snapshot FKs) stay stable.
        """
        submit = (
            job.submit_time or (details.submit_time if details else "") or ""
        ).strip()

        row = session.scalar(
            select(Job).where(
                Job.profile_name == profile_name,
                Job.job_id == job.job_id,
                Job.submit_time == submit,
            )
        )
        if row is None and submit:
            # The same run may have been recorded before its submit time was
            # known — adopt that placeholder row instead of creating a dup.
            row = session.scalar(
                select(Job).where(
                    Job.profile_name == profile_name,
                    Job.job_id == job.job_id,
                    Job.submit_time == "",
                )
            )

        gpu_count, gpu_type = _parse_gres(job.gres)
        if details and details.num_gpus:
            gpu_count = details.num_gpus
            gpu_type = details.gpu_type or gpu_type
        num_cpus = job.num_cpus
        if num_cpus is None and details and details.num_cpus:
            num_cpus = details.num_cpus
        mem_mb = job.mem_requested_mb
        if mem_mb is None and details and details.mem_requested:
            mem_mb = mem_str_to_mb(details.mem_requested)

        now = utcnow()
        if row is None:
            row = Job(profile_name=profile_name, job_id=job.job_id, first_seen=now)
            session.add(row)

        row.submit_time = submit
        row.name = job.name or row.name
        row.state = job.state or row.state
        row.work_dir = job.work_dir or row.work_dir
        row.gres = job.gres or row.gres
        if gpu_count is not None:
            row.gpu_count = gpu_count
        if gpu_type:
            row.gpu_type = gpu_type
        if num_cpus is not None:
            row.num_cpus = num_cpus
        if mem_mb is not None:
            row.mem_requested_mb = mem_mb
        if job.qos:
            row.qos = job.qos
        if job.priority is not None:
            row.priority = job.priority
        elapsed = _elapsed_seconds(job.time)
        if elapsed is not None:
            row.elapsed_seconds = elapsed
        if details:
            row.partition = details.partition or row.partition
            row.node_list = details.node_list or row.node_list
            row.time_limit = details.time_limit or row.time_limit
            row.start_time = details.start_time or row.start_time
            row.end_time = details.end_time or row.end_time
            row.command = details.command or row.command
            row.stdout_path = details.stdout_path or row.stdout_path
            row.stderr_path = details.stderr_path or row.stderr_path
        row.last_seen = now

        session.flush()
        return row.id

    def record_snapshot(
        self,
        session: Session,
        job_pk: int,
        job: SlurmJob,
        captured_at: datetime,
        details: Optional[JobDetails] = None,
    ) -> None:
        """Append a usage snapshot. Measured-utilization fields come from ``details``."""
        gpu_count, _ = _parse_gres(job.gres)
        if details and details.num_gpus:
            gpu_count = details.num_gpus
        num_cpus = job.num_cpus
        if num_cpus is None and details and details.num_cpus:
            num_cpus = details.num_cpus
        mem_mb = job.mem_requested_mb
        if mem_mb is None and details and details.mem_requested:
            mem_mb = mem_str_to_mb(details.mem_requested)

        cpu_util_avg: Optional[int] = None
        gpu_util_avg: Optional[int] = None
        mem_used_mb: Optional[int] = None
        if details:
            if details.total_cpu:
                cpu_util_avg = round(details.cpu_percentage)
            if details.gpus:
                gpu_util_avg = round(
                    sum(g.utilization for g in details.gpus) / len(details.gpus)
                )
            if details.mem_used:
                used_bytes = parse_mem_bytes(details.mem_used)
                if used_bytes:
                    mem_used_mb = used_bytes // (1024 * 1024)

        session.add(
            UsageSnapshot(
                job_pk=job_pk,
                captured_at=captured_at,
                state=job.state,
                elapsed_seconds=_elapsed_seconds(job.time),
                gpu_count=gpu_count,
                num_cpus=num_cpus,
                mem_requested_mb=mem_mb,
                cpu_util_avg=cpu_util_avg,
                gpu_util_avg=gpu_util_avg,
                mem_used_mb=mem_used_mb,
            )
        )

    def _record_terminal_snapshot_once(
        self,
        session: Session,
        job_pk: int,
        job: SlurmJob,
        captured_at: datetime,
    ) -> None:
        """Append one terminal-state snapshot for a run, once."""
        latest_state = session.scalar(
            select(UsageSnapshot.state)
            .where(UsageSnapshot.job_pk == job_pk)
            .order_by(UsageSnapshot.captured_at.desc(), UsageSnapshot.id.desc())
            .limit(1)
        )
        if latest_state in TERMINAL_STATES:
            return
        self.record_snapshot(session, job_pk, job, captured_at)

    # ── favourites ────────────────────────────────────────────────────────

    def get_job_pk(
        self, session: Session, profile_name: str, job_id: str, submit_time: str
    ) -> Optional[int]:
        """Resolve a run's surrogate PK by natural key, if it exists."""
        return session.scalar(
            select(Job.id).where(
                Job.profile_name == profile_name,
                Job.job_id == job_id,
                Job.submit_time == (submit_time or "").strip(),
            )
        )

    def favourite_state(self, session: Session, job_pk: int) -> tuple[bool, str]:
        """Return ``(is_favourite, note)`` for a run."""
        fav = session.scalar(select(Favourite).where(Favourite.job_pk == job_pk))
        if fav is None:
            return False, ""
        return True, fav.note

    def set_favourite(
        self,
        session: Session,
        job_pk: int,
        favourite: bool,
        note: Optional[str] = None,
    ) -> None:
        """Star or unstar a run (keyed on the surrogate PK)."""
        existing = session.scalar(select(Favourite).where(Favourite.job_pk == job_pk))
        if favourite:
            if existing is None:
                session.add(Favourite(job_pk=job_pk, note=note or ""))
            elif note is not None:
                existing.note = note
        elif existing is not None:
            session.delete(existing)
        session.commit()

    def set_note(self, session: Session, job_pk: int, note: str) -> None:
        """Set a run's note, starring it if it was not already a favourite."""
        existing = session.scalar(select(Favourite).where(Favourite.job_pk == job_pk))
        if existing is None:
            session.add(Favourite(job_pk=job_pk, note=note))
        else:
            existing.note = note
        session.commit()

    # ── reads (history-screen worker) ─────────────────────────────────────

    @staticmethod
    def _to_job_run(job: Job, fav: Favourite | None) -> JobRun:
        return JobRun(
            pk=job.id,
            profile_name=job.profile_name,
            job_id=job.job_id,
            name=job.name,
            state=job.state,
            submit_time=job.submit_time,
            start_time=job.start_time,
            end_time=job.end_time,
            elapsed_seconds=job.elapsed_seconds,
            num_cpus=job.num_cpus,
            gpu_count=job.gpu_count,
            gpu_type=job.gpu_type,
            mem_requested_mb=job.mem_requested_mb,
            partition=job.partition,
            work_dir=job.work_dir,
            stdout_path=job.stdout_path,
            stderr_path=job.stderr_path,
            favourite=fav is not None,
            note=fav.note if fav is not None else None,
            last_seen=job.last_seen,
        )

    def get_run_by_pk(self, session: Session, job_pk: int) -> Optional[JobRun]:
        """Return one run by surrogate PK as a detached DTO."""
        row = session.execute(
            select(Job, Favourite)
            .outerjoin(Favourite, Favourite.job_pk == Job.id)
            .where(Job.id == job_pk)
            .limit(1)
        ).first()
        if row is None:
            return None
        job, fav = row
        return self._to_job_run(job, fav)

    def latest_run_for_job(
        self, session: Session, profile_name: str, job_id: str
    ) -> Optional[JobRun]:
        """Return the most recently-seen run for ``(profile_name, job_id)``."""
        row = session.execute(
            select(Job, Favourite)
            .outerjoin(Favourite, Favourite.job_pk == Job.id)
            .where(Job.profile_name == profile_name, Job.job_id == job_id)
            .order_by(Job.last_seen.desc(), Job.id.desc())
            .limit(1)
        ).first()
        if row is None:
            return None
        job, fav = row
        return self._to_job_run(job, fav)

    def summarize_run_snapshots(self, session: Session, job_pk: int) -> SnapshotSummary:
        """Return aggregate metrics for one run's usage snapshot timeline."""
        rows = session.scalars(
            select(UsageSnapshot)
            .where(UsageSnapshot.job_pk == job_pk)
            .order_by(UsageSnapshot.captured_at.asc(), UsageSnapshot.id.asc())
        ).all()
        if not rows:
            return SnapshotSummary()

        cpu_values = [r.cpu_util_avg for r in rows if r.cpu_util_avg is not None]
        gpu_values = [r.gpu_util_avg for r in rows if r.gpu_util_avg is not None]
        mem_values = [r.mem_used_mb for r in rows if r.mem_used_mb is not None]
        latest = rows[-1]

        return SnapshotSummary(
            snapshot_count=len(rows),
            first_captured_at=rows[0].captured_at,
            last_captured_at=latest.captured_at,
            latest_cpu_util=latest.cpu_util_avg,
            avg_cpu_util=(
                round(sum(cpu_values) / len(cpu_values), 1) if cpu_values else None
            ),
            peak_cpu_util=max(cpu_values) if cpu_values else None,
            latest_gpu_util=latest.gpu_util_avg,
            avg_gpu_util=(
                round(sum(gpu_values) / len(gpu_values), 1) if gpu_values else None
            ),
            peak_gpu_util=max(gpu_values) if gpu_values else None,
            latest_mem_used_mb=latest.mem_used_mb,
            peak_mem_used_mb=max(mem_values) if mem_values else None,
        )

    def get_run_snapshots(self, session: Session, job_pk: int) -> list[SnapshotPoint]:
        """Return the full snapshot timeline for one run (oldest first)."""
        rows = session.scalars(
            select(UsageSnapshot)
            .where(UsageSnapshot.job_pk == job_pk)
            .order_by(UsageSnapshot.captured_at.asc(), UsageSnapshot.id.asc())
        ).all()
        return [
            SnapshotPoint(
                captured_at=row.captured_at,
                state=row.state,
                elapsed_seconds=row.elapsed_seconds,
                num_cpus=row.num_cpus,
                gpu_count=row.gpu_count,
                cpu_util_avg=row.cpu_util_avg,
                gpu_util_avg=row.gpu_util_avg,
                mem_requested_mb=row.mem_requested_mb,
                mem_used_mb=row.mem_used_mb,
            )
            for row in rows
        ]

    def query_runs(
        self,
        session: Session,
        *,
        profile: Optional[str] = None,
        states: Optional[list[str]] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        favourites_only: bool = False,
        search: Optional[str] = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[JobRun]:
        """Return matching runs (newest last-seen first) as detached DTOs."""
        stmt = select(Job, Favourite).outerjoin(Favourite, Favourite.job_pk == Job.id)
        if profile:
            stmt = stmt.where(Job.profile_name == profile)
        if states:
            stmt = stmt.where(Job.state.in_(states))
        if since is not None:
            stmt = stmt.where(Job.last_seen >= since)
        if until is not None:
            stmt = stmt.where(Job.last_seen <= until)
        if favourites_only:
            stmt = stmt.where(Favourite.id.isnot(None))
        if search:
            like = f"%{search}%"
            stmt = stmt.where(Job.name.ilike(like) | Job.job_id.ilike(like))
        stmt = (
            stmt.order_by(Job.last_seen.desc(), Job.id.desc())
            .limit(limit)
            .offset(offset)
        )

        runs: list[JobRun] = []
        for job, fav in session.execute(stmt).all():
            runs.append(self._to_job_run(job, fav))
        return runs

    def aggregate_usage(
        self,
        session: Session,
        *,
        profile: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> UsageTotals:
        """Sum allocated resource-hours over the matching runs.

        Computed from the ``jobs`` table (final allocation × elapsed), so the
        result is independent of how many snapshots were taken.
        """
        stmt = select(Job)
        if profile:
            stmt = stmt.where(Job.profile_name == profile)
        if since is not None:
            stmt = stmt.where(Job.last_seen >= since)
        if until is not None:
            stmt = stmt.where(Job.last_seen <= until)
        jobs = session.scalars(stmt).all()

        groups: dict[Optional[str], dict[str, float]] = {}

        def _accumulate(key: Optional[str], job: Job) -> None:
            acc = groups.setdefault(
                key, {"gpu": 0.0, "cpu": 0.0, "mem": 0.0, "count": 0}
            )
            hours = (job.elapsed_seconds or 0) / 3600.0
            acc["gpu"] += (job.gpu_count or 0) * hours
            acc["cpu"] += (job.num_cpus or 0) * hours
            acc["mem"] += (job.mem_requested_mb or 0) / 1024.0 * hours
            acc["count"] += 1

        for job in jobs:
            _accumulate(None, job)
            if profile is None:
                _accumulate(job.profile_name, job)

        avg_util = self._avg_gpu_util(session, profile, since, until)

        overall = groups.get(None, {"gpu": 0.0, "cpu": 0.0, "mem": 0.0, "count": 0})
        per_profile: list[UsageTotals] = []
        if profile is None:
            named = sorted((k, v) for k, v in groups.items() if k is not None)
            for name, acc in named:
                per_profile.append(
                    UsageTotals(
                        profile_name=name,
                        gpu_hours=round(acc["gpu"], 2),
                        cpu_hours=round(acc["cpu"], 2),
                        mem_gb_hours=round(acc["mem"], 2),
                        avg_gpu_util=None,
                        job_count=int(acc["count"]),
                    )
                )

        return UsageTotals(
            profile_name=profile,
            gpu_hours=round(overall["gpu"], 2),
            cpu_hours=round(overall["cpu"], 2),
            mem_gb_hours=round(overall["mem"], 2),
            avg_gpu_util=avg_util,
            job_count=int(overall["count"]),
            per_profile=per_profile,
        )

    def _avg_gpu_util(
        self,
        session: Session,
        profile: Optional[str],
        since: Optional[datetime],
        until: Optional[datetime],
    ) -> Optional[float]:
        stmt = select(func.avg(UsageSnapshot.gpu_util_avg)).where(
            UsageSnapshot.gpu_util_avg.isnot(None)
        )
        if profile or since is not None or until is not None:
            stmt = stmt.join(Job, Job.id == UsageSnapshot.job_pk)
            if profile:
                stmt = stmt.where(Job.profile_name == profile)
            if since is not None:
                stmt = stmt.where(UsageSnapshot.captured_at >= since)
            if until is not None:
                stmt = stmt.where(UsageSnapshot.captured_at <= until)
        value = session.scalar(stmt)
        return round(float(value), 1) if value is not None else None

    # ── retention ─────────────────────────────────────────────────────────

    def prune(
        self, session: Session, retention_days: int, now: Optional[datetime] = None
    ) -> int:
        """Delete non-favourite runs older than the window. Snapshots cascade."""
        if retention_days <= 0:
            return 0
        cutoff = (now or utcnow()) - timedelta(days=retention_days)
        favourited = select(Favourite.job_pk)
        result = session.execute(
            delete(Job).where(Job.last_seen < cutoff, Job.id.notin_(favourited))
        )
        session.commit()
        return result.rowcount or 0
