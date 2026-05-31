"""FontAwesome icon helpers (via qtawesome).

Two flavours:

- :func:`nav_icon` — sidebar entries. Coloured with a neutral grey that reads on
  both the light and dark sidebar, switching to white when the row is selected
  (the selected row sits on the accent colour). Theme-switch-proof.
- :func:`button_icon` — toolbar/button glyphs, tinted to the current palette text
  colour so they match the surrounding text.

Every lookup degrades to an empty ``QIcon`` if qtawesome (or a glyph) is
unavailable, so the GUI never fails to build over a missing icon.
"""

from typing import Optional

from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import QApplication

# Neutral grey readable on both light (#eceef1) and dark (#26282c) sidebars.
_NAV_COLOR = "#8b949e"
_NAV_SELECTED = "#ffffff"


def _qta_icon(name: str, **kwargs) -> QIcon:
    try:
        import qtawesome as qta

        return qta.icon(name, **kwargs)
    except Exception:  # noqa: BLE001 — missing lib / unknown glyph → no icon
        return QIcon()


def nav_icon(name: str) -> QIcon:
    """A sidebar icon: grey normally, white when its row is selected/active."""
    return _qta_icon(
        name, color=_NAV_COLOR, color_active=_NAV_SELECTED, color_selected=_NAV_SELECTED
    )


def button_icon(name: str, color: Optional[str] = None) -> QIcon:
    """A button/toolbar icon tinted to ``color`` (default: palette text colour)."""
    if color is None:
        app = QApplication.instance()
        if app is not None:
            color = app.palette().color(QPalette.ColorRole.WindowText).name()
        else:  # pragma: no cover — no running app
            color = _NAV_COLOR
    return _qta_icon(name, color=color)
