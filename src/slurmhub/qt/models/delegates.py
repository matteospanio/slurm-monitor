"""Item delegates for custom cell rendering."""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from slurmhub.qt.theme import state_color


class StateBadgeDelegate(QStyledItemDelegate):
    """Render a Slurm job state as a rounded, colour-coded pill."""

    def paint(self, painter: QPainter, option, index) -> None:
        self.initStyleOption(option, index)
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        if text:
            color = state_color(text)
            fm = option.fontMetrics
            pad_x, pad_y = 8, 3
            width = fm.horizontalAdvance(text) + 2 * pad_x
            height = fm.height() + 2 * pad_y
            top = option.rect.center().y() - height // 2
            badge = QRect(option.rect.left() + 6, top, width, height)

            fill = QColor(color)
            fill.setAlpha(46)
            painter.setBrush(fill)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(badge, 7, 7)

            painter.setPen(color)
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)

        painter.restore()
