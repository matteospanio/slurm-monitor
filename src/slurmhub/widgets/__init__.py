"""Textual widgets for slurmhub."""

from slurmhub.widgets.connection_status import ConnectionStatus
from slurmhub.widgets.filter_bar import FilterBar
from slurmhub.widgets.job_detail import JobDetail
from slurmhub.widgets.job_table import JobTable
from slurmhub.widgets.status_bar import StatusBar

__all__ = [
    "ConnectionStatus",
    "FilterBar",
    "JobDetail",
    "JobTable",
    "StatusBar",
]
