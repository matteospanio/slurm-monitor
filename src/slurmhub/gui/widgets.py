"""Small reusable custom widgets for the GUI."""

from typing import Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget

from slurmhub.gui.theme import bar_color, token


class CapacityBar(QWidget):
    """A labelled utilisation bar (CPU / GPU / memory) coloured by threshold."""

    def __init__(self, label: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._label = label
        self._percentage = 0.0
        self._detail = ""
        self.setMinimumHeight(52)

    def set_value(self, percentage: float, detail: str = "") -> None:
        self._percentage = max(0.0, min(100.0, float(percentage)))
        self._detail = detail
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)

        text_color = token("text")
        muted = token("text_muted")

        # Header row: label (left) + detail/percentage (right).
        font = QFont(self.font())
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(
            rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, self._label
        )
        painter.setFont(self.font())
        painter.setPen(muted)
        right_text = self._detail or f"{self._percentage:.0f}%"
        painter.drawText(
            rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight, right_text
        )

        # Bar track + fill.
        bar_h = 12
        bar_top = rect.bottom() - bar_h
        track = QRectF(rect.left(), bar_top, rect.width(), bar_h)
        track_color = token("surface2")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, 6, 6)

        if self._percentage > 0:
            fill_w = max(bar_h, rect.width() * self._percentage / 100.0)
            fill = QRectF(rect.left(), bar_top, fill_w, bar_h)
            painter.setBrush(bar_color(self._percentage))
            painter.drawRoundedRect(fill, 6, 6)

        painter.end()
