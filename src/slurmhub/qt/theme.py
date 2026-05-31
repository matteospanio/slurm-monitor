"""Hand-rolled light/dark theming for the Qt GUI.

A single QSS template (``resources/theme.qss``) is substituted with a per-mode
token table and applied app-wide, alongside a matching ``QPalette`` so native
controls pick up the colours too. ``"auto"`` follows the OS colour scheme (Qt
6.5+) and re-applies live when it changes. The chosen mode is persisted via
``QSettings`` so the Settings screen and the next launch agree.

State colours (running/pending/failed/completed) are exported as
:data:`STATE_COLORS` for the table delegates to use.
"""

from pathlib import Path
from string import Template
from typing import Optional

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

_QSS_PATH = Path(__file__).parent / "resources" / "theme.qss"

# Token tables. Ported from the Textual ``app.tcss`` palette + state colours.
TOKENS: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#1e1f22",
        "surface": "#2b2d31",
        "surface2": "#26282c",
        "text": "#e6e6e6",
        "text_muted": "#9aa0a6",
        "border": "#3a3c40",
        "accent": "#4f8cff",
        "accent_text": "#ffffff",
        "running": "#3fb950",
        "pending": "#d29922",
        "failed": "#f85149",
        "completed": "#8b949e",
    },
    "light": {
        "bg": "#f5f6f8",
        "surface": "#ffffff",
        "surface2": "#eceef1",
        "text": "#1f2328",
        "text_muted": "#656d76",
        "border": "#d0d7de",
        "accent": "#2f6feb",
        "accent_text": "#ffffff",
        "running": "#1a7f37",
        "pending": "#9a6700",
        "failed": "#cf222e",
        "completed": "#6e7781",
    },
}

# Slurm state → token key, for the table delegates. Unknown states fall back to
# the muted text colour.
STATE_TOKENS = {
    "RUNNING": "running",
    "PENDING": "pending",
    "COMPLETED": "completed",
    "COMPLETING": "running",
    "FAILED": "failed",
    "CANCELLED": "failed",
    "TIMEOUT": "failed",
    "OUT_OF_MEMORY": "failed",
    "NODE_FAIL": "failed",
}


def _settings() -> QSettings:
    return QSettings("slurmhub", "SlurmHub")


def load_theme_preference() -> str:
    """Return the saved theme mode (``light`` / ``dark`` / ``auto``)."""
    value = _settings().value("theme/mode", "auto")
    return value if value in ("light", "dark", "auto") else "auto"


def save_theme_preference(mode: str) -> None:
    if mode in ("light", "dark", "auto"):
        _settings().setValue("theme/mode", mode)


def resolve_mode(mode: str) -> str:
    """Resolve ``"auto"`` to ``"light"`` / ``"dark"`` via the OS colour scheme."""
    if mode != "auto":
        return mode if mode in TOKENS else "dark"
    hints = QApplication.styleHints()
    scheme = getattr(hints, "colorScheme", lambda: Qt.ColorScheme.Unknown)()
    return "light" if scheme == Qt.ColorScheme.Light else "dark"


def state_color(state: str, mode: Optional[str] = None) -> QColor:
    """Return the :class:`QColor` for a Slurm job ``state`` under the theme."""
    resolved = resolve_mode(mode or load_theme_preference())
    tokens = TOKENS[resolved]
    key = STATE_TOKENS.get((state or "").upper(), "text_muted")
    return QColor(tokens[key])


def _build_qss(tokens: dict[str, str]) -> str:
    template = Template(_QSS_PATH.read_text(encoding="utf-8"))
    return template.safe_substitute(tokens)


def _build_palette(tokens: dict[str, str]) -> QPalette:
    pal = QPalette()
    bg, surface, text, muted = (
        QColor(tokens["bg"]),
        QColor(tokens["surface"]),
        QColor(tokens["text"]),
        QColor(tokens["text_muted"]),
    )
    accent = QColor(tokens["accent"])
    pal.setColor(QPalette.ColorRole.Window, bg)
    pal.setColor(QPalette.ColorRole.WindowText, text)
    pal.setColor(QPalette.ColorRole.Base, surface)
    pal.setColor(QPalette.ColorRole.AlternateBase, bg)
    pal.setColor(QPalette.ColorRole.Text, text)
    pal.setColor(QPalette.ColorRole.Button, surface)
    pal.setColor(QPalette.ColorRole.ButtonText, text)
    pal.setColor(QPalette.ColorRole.ToolTipBase, surface)
    pal.setColor(QPalette.ColorRole.ToolTipText, text)
    pal.setColor(QPalette.ColorRole.PlaceholderText, muted)
    pal.setColor(QPalette.ColorRole.Highlight, accent)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(tokens["accent_text"]))
    pal.setColor(QPalette.ColorRole.Link, accent)
    return pal


def apply_theme(app: QApplication, mode: str = "auto") -> str:
    """Apply ``mode`` to ``app`` (palette + stylesheet); return the resolved mode."""
    resolved = resolve_mode(mode)
    tokens = TOKENS[resolved]
    app.setPalette(_build_palette(tokens))
    app.setStyleSheet(_build_qss(tokens))
    return resolved
