"""initial job-history schema

Revision ID: 0001
Revises:
Create Date: 2026-05-31

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_name", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column(
            "submit_time",
            sa.String(length=32),
            nullable=False,
            server_default="",
        ),
        sa.Column("name", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("state", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("work_dir", sa.Text(), nullable=True),
        sa.Column("gres", sa.String(length=128), nullable=True),
        sa.Column("gpu_count", sa.Integer(), nullable=True),
        sa.Column("gpu_type", sa.String(length=32), nullable=True),
        sa.Column("num_cpus", sa.Integer(), nullable=True),
        sa.Column("mem_requested_mb", sa.Integer(), nullable=True),
        sa.Column("partition", sa.String(length=64), nullable=True),
        sa.Column("node_list", sa.String(length=256), nullable=True),
        sa.Column("qos", sa.String(length=64), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("time_limit", sa.String(length=32), nullable=True),
        sa.Column("elapsed_seconds", sa.Integer(), nullable=True),
        sa.Column("start_time", sa.String(length=32), nullable=True),
        sa.Column("end_time", sa.String(length=32), nullable=True),
        sa.Column("command", sa.Text(), nullable=True),
        sa.Column("stdout_path", sa.Text(), nullable=True),
        sa.Column("stderr_path", sa.Text(), nullable=True),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_name", "job_id", "submit_time", name="uq_job_natural"
        ),
    )
    op.create_index(
        "ix_jobs_profile_state", "jobs", ["profile_name", "state"], unique=False
    )
    op.create_index(
        "ix_jobs_profile_lastseen",
        "jobs",
        ["profile_name", "last_seen"],
        unique=False,
    )
    op.create_index("ix_jobs_lastseen", "jobs", ["last_seen"], unique=False)

    op.create_table(
        "usage_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_pk", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=True),
        sa.Column("elapsed_seconds", sa.Integer(), nullable=True),
        sa.Column("gpu_count", sa.Integer(), nullable=True),
        sa.Column("num_cpus", sa.Integer(), nullable=True),
        sa.Column("mem_requested_mb", sa.Integer(), nullable=True),
        sa.Column("gpu_util_avg", sa.Integer(), nullable=True),
        sa.Column("mem_used_mb", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["job_pk"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_snap_job_time",
        "usage_snapshots",
        ["job_pk", "captured_at"],
        unique=False,
    )

    op.create_table(
        "favourites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_pk", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_pk"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_pk", name="uq_favourite_job"),
    )


def downgrade() -> None:
    op.drop_table("favourites")
    op.drop_index("ix_snap_job_time", table_name="usage_snapshots")
    op.drop_table("usage_snapshots")
    op.drop_index("ix_jobs_lastseen", table_name="jobs")
    op.drop_index("ix_jobs_profile_lastseen", table_name="jobs")
    op.drop_index("ix_jobs_profile_state", table_name="jobs")
    op.drop_table("jobs")
