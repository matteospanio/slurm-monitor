"""Table model exposing a list of :class:`SlurmJob` to a ``QTableView``.

The model is read-only and rebuilt wholesale on each refresh (the job lists are
small). Sorting is delegated to a ``QSortFilterProxyModel`` driven by
:data:`SORT_ROLE`, which returns a typed key per column (ints for IDs/CPUs/mem,
seconds for elapsed time) so columns sort numerically rather than lexically.
"""

from typing import Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from slurmhub.core.job_aggregator import _job_sort_key
from slurmhub.slurm.squeue import SlurmJob
from slurmhub.slurm.util import time_to_seconds

# Custom roles.
JOB_ROLE = Qt.ItemDataRole.UserRole       # the SlurmJob for a row
SORT_ROLE = Qt.ItemDataRole.UserRole + 1  # typed sort key for a cell

# (header, attribute key). The attribute key also selects the cell formatter.
COLUMNS = [
    ("Job ID", "job_id"),
    ("Name", "name"),
    ("State", "state"),
    ("Time", "time"),
    ("CPUs", "cpus"),
    ("GPU", "gpu"),
    ("Memory", "mem"),
]

_NUMERIC_COLUMNS = {"cpus", "mem"}


def format_mem_mb(mb: Optional[int]) -> str:
    """Format a megabyte count as a compact human string (``16G`` / ``512M``)."""
    if not mb:
        return "—"
    if mb >= 1024:
        gb = mb / 1024
        return f"{gb:.0f}G" if gb == int(gb) else f"{gb:.1f}G"
    return f"{mb}M"


class JobsModel(QAbstractTableModel):
    def __init__(self, jobs: Optional[list[SlurmJob]] = None) -> None:
        super().__init__()
        self._jobs: list[SlurmJob] = jobs or []

    # ── data plumbing ────────────────────────────────────────────────
    def set_jobs(self, jobs: list[SlurmJob]) -> None:
        self.beginResetModel()
        self._jobs = jobs
        self.endResetModel()

    def job_at(self, row: int) -> Optional[SlurmJob]:
        if 0 <= row < len(self._jobs):
            return self._jobs[row]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._jobs)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(COLUMNS)
        ):
            return COLUMNS[section][0]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        job = self._jobs[index.row()]
        key = COLUMNS[index.column()][1]

        if role == JOB_ROLE:
            return job
        if role == SORT_ROLE:
            return self._sort_key(job, key)
        if role == Qt.ItemDataRole.TextAlignmentRole and key in _NUMERIC_COLUMNS:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(job, key)
        return None

    # ── formatting ───────────────────────────────────────────────────
    @staticmethod
    def _display(job: SlurmJob, key: str) -> str:
        if key == "job_id":
            return job.job_id
        if key == "name":
            return job.name
        if key == "state":
            return job.state
        if key == "time":
            return job.time
        if key == "cpus":
            return str(job.num_cpus) if job.num_cpus else "—"
        if key == "gpu":
            return job.gpu_display or "—"
        if key == "mem":
            return format_mem_mb(job.mem_requested_mb)
        return ""

    @staticmethod
    def _sort_key(job: SlurmJob, key: str):
        if key == "job_id":
            return _job_sort_key(job.job_id)
        if key == "time":
            return time_to_seconds(job.time)
        if key == "cpus":
            return job.num_cpus or 0
        if key == "mem":
            return job.mem_requested_mb or 0
        if key == "gpu":
            return job.gpu_display or ""
        if key == "name":
            return job.name.lower()
        if key == "state":
            return job.state
        return ""
