"""Shared rendering helpers for the TUI widgets."""

from rich.text import Text

# Bar characters for percentage rendering
BAR_FILLED = "█"
BAR_EMPTY = "░"
DEFAULT_BAR_WIDTH = 20


def render_bar(percentage: float, width: int = DEFAULT_BAR_WIDTH) -> Text:
    """Render a colored percentage bar with a trailing "%" label.

    Green below 70%, yellow 70-89%, red 90% and above. Clamps to [0, 100].
    """
    pct = max(0.0, min(100.0, percentage))
    filled = round(width * pct / 100)
    empty = width - filled

    if pct >= 90:
        color = "red"
    elif pct >= 70:
        color = "yellow"
    else:
        color = "green"

    bar = Text()
    bar.append(BAR_FILLED * filled, style=color)
    bar.append(BAR_EMPTY * empty, style="dim")
    bar.append(f" {pct:.1f}%")
    return bar
