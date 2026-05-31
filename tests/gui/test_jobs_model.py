"""Tests for the jobs table model: display formatting and sort keys."""

from PySide6.QtCore import Qt

from slurmhub.gui.models.jobs_model import (
    COLUMNS,
    JOB_ROLE,
    SORT_ROLE,
    JobsModel,
    format_mem_mb,
)
from slurmhub.slurm.squeue import SlurmJob


def _job(**kw) -> SlurmJob:
    base = dict(job_id="1", name="n", state="RUNNING", time="00:01")
    base.update(kw)
    return SlurmJob(**base)


def test_format_mem_mb():
    assert format_mem_mb(None) == "—"
    assert format_mem_mb(0) == "—"
    assert format_mem_mb(512) == "512M"
    assert format_mem_mb(16384) == "16G"
    assert format_mem_mb(1536) == "1.5G"


def test_row_and_column_counts():
    model = JobsModel([_job(job_id="1"), _job(job_id="2")])
    assert model.rowCount() == 2
    assert model.columnCount() == len(COLUMNS)


def test_display_values_and_job_role():
    job = _job(job_id="42", name="train", state="PENDING", time="00:30",
               num_cpus=8, gres="gpu:a100:2", mem_requested_mb=16384)
    model = JobsModel([job])

    def disp(col):
        return model.data(model.index(0, col), Qt.ItemDataRole.DisplayRole)

    assert disp(0) == "42"
    assert disp(1) == "train"
    assert disp(2) == "PENDING"
    assert disp(4) == "8"
    assert disp(5) == "2x a100"
    assert disp(6) == "16G"
    assert model.data(model.index(0, 0), JOB_ROLE) is job


def test_sort_role_is_numeric_for_id_and_time():
    model = JobsModel([_job(job_id="100", time="01:00"), _job(job_id="20", time="00:30")])
    # Job ID sort key compares numerically (100 > 20), not lexically.
    k0 = model.data(model.index(0, 0), SORT_ROLE)
    k1 = model.data(model.index(1, 0), SORT_ROLE)
    assert k0 > k1
    # Time sort key in seconds. Slurm elapsed "MM:SS": 01:00 → 60s, 00:30 → 30s.
    t0 = model.data(model.index(0, 3), SORT_ROLE)
    t1 = model.data(model.index(1, 3), SORT_ROLE)
    assert t0 == 60 and t1 == 30
