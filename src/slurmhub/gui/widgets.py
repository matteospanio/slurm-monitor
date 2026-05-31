"""Small reusable custom widgets for the GUI."""

from typing import Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from slurmhub.gui.theme import bar_color, token


class CapacityBar(QWidget):
    """A labelled utilisation bar (CPU / GPU / memory) coloured by threshold."""

    def __init__(self, label: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._label = label
        self._percentage = 0.0
        self._detail = ""
        self.setMinimumHeight(54)

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
        fill_color = bar_color(self._percentage)

        # Header row: label (left, bold) + detail (centre-right, muted) +
        # percentage (far right, in the bar colour so the eye links them).
        font = QFont(self.font())
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(
            rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, self._label
        )

        pct_text = f"{self._percentage:.0f}%"
        painter.setPen(fill_color)
        painter.drawText(
            rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight, pct_text
        )

        if self._detail:
            pct_w = painter.fontMetrics().horizontalAdvance(pct_text) + 12
            painter.setFont(self.font())
            painter.setPen(muted)
            painter.drawText(
                rect.adjusted(0, 0, -pct_w, 0),
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
                self._detail,
            )

        # Bar track + fill (both rounded; the fill sits flush on the track).
        bar_h = 10
        bar_top = rect.bottom() - bar_h
        radius = bar_h / 2
        track = QRectF(rect.left(), bar_top, rect.width(), bar_h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(token("surface2"))
        painter.drawRoundedRect(track, radius, radius)

        if self._percentage > 0:
            fill_w = max(bar_h, rect.width() * self._percentage / 100.0)
            fill = QRectF(rect.left(), bar_top, fill_w, bar_h)
            painter.setBrush(fill_color)
            painter.drawRoundedRect(fill, radius, radius)

        painter.end()


class StatTile(QFrame):
    """A compact metric card: a small upper label and a large value below.

    Used on the Queue / Cluster header strips so key numbers (running jobs,
    cluster CPU%, …) can be scanned at a glance instead of read from a run-on
    text line. ``accent`` tints the value (e.g. a state colour).
    """

    def __init__(
        self, label: str, value: str = "—", parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("StatTile")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(1)

        self._label = QLabel(label.upper())
        self._label.setObjectName("StatLabel")
        self._value = QLabel(value)
        self._value.setObjectName("StatValue")
        layout.addWidget(self._label)
        layout.addWidget(self._value)

    def set_value(self, value: str, accent: Optional[QColor] = None) -> None:
        self._value.setText(value)
        if accent is not None:
            self._value.setStyleSheet(f"color: {accent.name()};")
        else:
            self._value.setStyleSheet("")


class StatStrip(QWidget):
    """A horizontal row of :class:`StatTile`s, created on demand by key."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._tiles: dict[str, StatTile] = {}
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)

    def set_tile(
        self, key: str, label: str, value: str, accent: Optional[QColor] = None
    ) -> None:
        """Update (or create) the tile under ``key``."""
        tile = self._tiles.get(key)
        if tile is None:
            tile = StatTile(label)
            self._tiles[key] = tile
            self._layout.addWidget(tile)
        tile.set_value(value, accent)
