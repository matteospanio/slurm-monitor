"""SQLAlchemy ORM models for the job-history database.

Three tables back the history feature:

* :class:`Job` — one row per *run*, identified by a surrogate primary key and
  the natural key ``(profile_name, job_id, submit_time)``. Tagged with the
  profile/cluster it belongs to so a single database can hold every cluster.
* :class:`UsageSnapshot` — a time-series row appended each refresh cycle for an
  active job. Allocated fields (CPUs/GPUs/memory) come from ``squeue`` every
  cycle; measured-utilization fields are filled only by the slower utilization
  pass, so they are nullable.
* :class:`Favourite` — a star plus an optional free-text note, 1:1 with a run.

SQLAlchemy keeps the backend swappable; SQLite is the default. Schema changes
are applied by Alembic (``slurmhub.db.engine._run_migrations``), never by
``create_all``, so ``alembic_version`` is always stamped and future versions
stay retro-compatible.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Naive UTC now.

    Stored without tzinfo so SQLite's string comparisons (used by retention and
    range filters) stay consistent between stored values and query bounds.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Backwards-friendly alias used as the column ``default=`` callable.
_utcnow = utcnow


class Base(DeclarativeBase):
    """Declarative base for all history models."""


class Job(Base):
    """A single Slurm run, deduplicated on its natural key."""

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint(
            "profile_name", "job_id", "submit_time", name="uq_job_natural"
        ),
        Index("ix_jobs_profile_state", "profile_name", "state"),
        Index("ix_jobs_profile_lastseen", "profile_name", "last_seen"),
        Index("ix_jobs_lastseen", "last_seen"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_name: Mapped[str] = mapped_column(String(128), nullable=False)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Empty string (not NULL) so rows with an as-yet-unknown submit time do not
    # all count as distinct under the UNIQUE constraint (SQLite treats NULLs as
    # distinct). A real submit time is merged into the "" row in place later.
    submit_time: Mapped[str] = mapped_column(String(32), nullable=False, default="")

    name: Mapped[str] = mapped_column(String(256), default="")
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    work_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    gres: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gpu_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gpu_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    num_cpus: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mem_requested_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    partition: Mapped[str | None] = mapped_column(String(64), nullable=True)
    node_list: Mapped[str | None] = mapped_column(String(256), nullable=True)
    qos: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_limit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    elapsed_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    command: Mapped[str | None] = mapped_column(Text, nullable=True)
    stdout_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )

    snapshots: Mapped[list["UsageSnapshot"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    favourite: Mapped["Favourite | None"] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class UsageSnapshot(Base):
    """A point-in-time resource sample for an active run."""

    __tablename__ = "usage_snapshots"
    __table_args__ = (Index("ix_snap_job_time", "job_pk", "captured_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_pk: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    elapsed_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gpu_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_cpus: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mem_requested_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Measured utilization — only populated by the slower utilization pass.
    gpu_util_avg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mem_used_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)

    job: Mapped["Job"] = relationship(back_populates="snapshots")


class Favourite(Base):
    """A starred run with an optional note (1:1 with a :class:`Job`)."""

    __tablename__ = "favourites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_pk: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )

    job: Mapped["Job"] = relationship(back_populates="favourite")
