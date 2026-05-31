"""App/tray icon, painted at runtime so no binary asset is required.

Phase 7 can swap this for a real .png/.ico/.icns generated from the project
logo; for now a clean rounded-square "S" keeps the window, tray, and packaged
build self-contained.
"""

from functools import lru_cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap


@lru_cache(maxsize=1)
def app_icon() -> QIcon:
    pixmap = QPixmap(256, 256)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#2f6feb"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(16, 16, 224, 224), 48, 48)
    font = QFont()
    font.setBold(True)
    font.setPixelSize(150)
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "S")
    painter.end()
    return QIcon(pixmap)
