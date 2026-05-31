"""Textual widgets for slurmhub."""

from slurmhub.tui.widgets.connection_status import ConnectionStatus
from slurmhub.tui.widgets.filter_bar import FilterBar
from slurmhub.tui.widgets.job_detail import JobDetail
from slurmhub.tui.widgets.job_table import JobTable
from slurmhub.tui.widgets.status_bar import StatusBar

__all__ = [
    "ConnectionStatus",
    "FilterBar",
    "JobDetail",
    "JobTable",
    "StatusBar",
]
