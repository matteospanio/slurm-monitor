"""A reusable, read-only table model backed by an arbitrary row list.

Each column is described by a header and a getter callable; this keeps the
partition / node / (later) history tables to a column-spec list rather than a
bespoke model per table.
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

ROW_ROLE = Qt.ItemDataRole.UserRole  # the underlying row object


@dataclass
class Column:
    header: str
    getter: Callable[[Any], Any]
    numeric: bool = False


class SimpleTableModel(QAbstractTableModel):
    def __init__(
        self, columns: list[Column], rows: Optional[list] = None
    ) -> None:
        super().__init__()
        self._columns = columns
        self._rows: list = rows or []

    def set_rows(self, rows: list) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row_at(self, row: int):
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._columns)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(self._columns)
        ):
            return self._columns[section].header
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        column = self._columns[index.column()]
        row = self._rows[index.row()]
        if role == ROW_ROLE:
            return row
        if role == Qt.ItemDataRole.DisplayRole:
            return str(column.getter(row))
        if role == Qt.ItemDataRole.TextAlignmentRole and column.numeric:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None
