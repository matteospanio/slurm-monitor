"""The Cluster Status screen: capacity bars + partition and node tables.

All data comes from the active profile's most recent ``fetch_sinfo`` result
(``ClusterCapacity`` / ``PartitionStats`` / ``NodeStats``), which the controller
refreshes on its slower (~60 s) cadence and on the first fetch.
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from slurmhub.gui.controller import AppController
from slurmhub.gui.icons import button_icon
from slurmhub.gui.models.jobs_model import format_mem_mb
from slurmhub.gui.models.simple_table import Column, SimpleTableModel
from slurmhub.gui.theme import token
from slurmhub.gui.widgets import CapacityBar, StatStrip

_PARTITION_COLUMNS = [
    Column("Partition", lambda p: p.name),
    Column("Nodes", lambda p: p.nodes_total, numeric=True),
    Column("Idle", lambda p: p.nodes_idle, numeric=True),
    Column("Mixed", lambda p: p.nodes_mixed, numeric=True),
    Column("Alloc", lambda p: p.nodes_alloc, numeric=True),
    Column("Down", lambda p: p.nodes_down, numeric=True),
    Column("CPUs", lambda p: f"{p.cpus_alloc}/{p.cpus_total}", numeric=True),
    Column("GPUs", lambda p: f"{p.gpus_used}/{p.gpus_total}", numeric=True),
    Column("Memory", lambda p: format_mem_mb(p.mem_total_mb), numeric=True),
    Column("Avail", lambda p: "up" if p.available else "down"),
]

_NODE_COLUMNS = [
    Column("Node", lambda n: n.name),
    Column("Partition", lambda n: n.partition),
    Column("State", lambda n: n.state),
    Column("CPUs", lambda n: f"{n.cpus_alloc}/{n.cpus_total}", numeric=True),
    Column("Free mem", lambda n: format_mem_mb(n.mem_free_mb), numeric=True),
    Column("Total mem", lambda n: format_mem_mb(n.mem_total_mb), numeric=True),
    Column("GPUs", lambda n: f"{n.gpus_used}/{n.gpus_total}", numeric=True),
    Column("Reason", lambda n: n.reason or ""),
]


def _table(model: SimpleTableModel) -> QTableView:
    view = QTableView()
    view.setModel(model)
    view.setAlternatingRowColors(True)
    view.setShowGrid(False)
    view.setSelectionMode(QTableView.SelectionMode.NoSelection)
    view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
    view.verticalHeader().setVisible(False)
    view.horizontalHeader().setStretchLastSection(True)
    view.horizontalHeader().setSectionResizeMode(
        0, QHeaderView.ResizeMode.ResizeToContents
    )
    return view


class ClusterView(QWidget):
    def __init__(
        self, controller: AppController, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self._build_ui()
        self._connect_signals()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        heading.setSpacing(1)
        title = QLabel("Cluster status")
        title.setObjectName("ViewTitle")
        heading.addWidget(title)
        self.nodes_summary = QLabel("")
        self.nodes_summary.setObjectName("HeaderStatus")
        heading.addWidget(self.nodes_summary)
        header.addLayout(heading)
        header.addStretch(1)
        refresh = QPushButton(button_icon("fa5s.sync-alt"), "Refresh")
        refresh.clicked.connect(self.controller.force_refresh_active)
        header.addWidget(refresh, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        self.node_tiles = StatStrip()
        layout.addWidget(self.node_tiles)

        bars_card = QFrame()
        bars_card.setObjectName("JobCard")
        bars_layout = QVBoxLayout(bars_card)
        bars_layout.setContentsMargins(16, 14, 16, 14)
        bars_title = QLabel("Utilisation")
        bars_title.setObjectName("JobCardTitle")
        bars_layout.addWidget(bars_title)
        bars = QHBoxLayout()
        bars.setSpacing(22)
        self.cpu_bar = CapacityBar("CPU")
        self.gpu_bar = CapacityBar("GPU")
        self.mem_bar = CapacityBar("Memory")
        for bar in (self.cpu_bar, self.gpu_bar, self.mem_bar):
            bars.addWidget(bar)
        bars_layout.addLayout(bars)
        layout.addWidget(bars_card)

        self.partitions_model = SimpleTableModel(_PARTITION_COLUMNS)
        self.nodes_model = SimpleTableModel(_NODE_COLUMNS)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._group("Partitions", self.partitions_model))
        splitter.addWidget(self._group("Nodes", self.nodes_model))
        layout.addWidget(splitter, 1)

    def _group(self, title: str, model: SimpleTableModel) -> QGroupBox:
        box = QGroupBox(title)
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(6, 6, 6, 6)
        box_layout.addWidget(_table(model))
        return box

    def _connect_signals(self) -> None:
        self.controller.jobsUpdated.connect(self._on_updated)
        self.controller.activeProfileChanged.connect(lambda _n: self.reload())

    def _on_updated(self, name: str) -> None:
        if name == self.controller.active_profile:
            self.reload()

    def reload(self) -> None:
        session = self.controller.session()
        if session is None:
            return
        cap = session.cluster_capacity
        if cap is not None:
            self.cpu_bar.set_value(
                cap.cpu_percentage, f"{cap.cpus_used}/{cap.cpus_total} cores"
            )
            self.gpu_bar.set_value(
                cap.gpu_percentage, f"{cap.gpus_used}/{cap.gpus_total} GPUs"
            )
            self.mem_bar.set_value(
                cap.mem_percentage,
                f"{format_mem_mb(cap.mem_used_mb)}/{format_mem_mb(cap.mem_total_mb)}",
            )
            self.nodes_summary.setText(
                f"{cap.nodes_up} up   •   {cap.nodes_down} down   •   "
                f"{cap.nodes_drain} drain   •   updated {cap.fetched_at}"
            )
            total = cap.nodes_up + cap.nodes_down + cap.nodes_drain
            self.node_tiles.set_tile("total", "Nodes", str(total))
            self.node_tiles.set_tile(
                "up", "Online", str(cap.nodes_up),
                token("running") if cap.nodes_up else None,
            )
            self.node_tiles.set_tile(
                "down", "Down", str(cap.nodes_down),
                token("failed") if cap.nodes_down else None,
            )
            self.node_tiles.set_tile(
                "drain", "Draining", str(cap.nodes_drain),
                token("pending") if cap.nodes_drain else None,
            )
        else:
            self.nodes_summary.setText("Waiting for cluster data…")

        self.partitions_model.set_rows(session.partitions)
        self.nodes_model.set_rows(session.nodes)
