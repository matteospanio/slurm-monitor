"""Textual widgets for Slurm Monitor."""

from slurm_monitor.widgets.connection_status import ConnectionStatus
from slurm_monitor.widgets.filter_bar import FilterBar
from slurm_monitor.widgets.job_detail import JobDetail
from slurm_monitor.widgets.job_table import JobTable
from slurm_monitor.widgets.status_bar import StatusBar

__all__ = [
    "ConnectionStatus",
    "FilterBar",
    "JobDetail",
    "JobTable",
    "StatusBar",
]
