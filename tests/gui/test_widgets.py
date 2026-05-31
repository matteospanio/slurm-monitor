"""Tests for the reusable presentational widgets (stat tiles, capacity bar)."""

from PySide6.QtGui import QColor

from slurmhub.gui.widgets import CapacityBar, StatStrip, StatTile


def test_stat_tile_sets_label_and_value(qtbot):
    tile = StatTile("Running", "3")
    qtbot.addWidget(tile)
    assert tile._label.text() == "RUNNING"  # labels are upper-cased
    assert tile._value.text() == "3"

    tile.set_value("7")
    assert tile._value.text() == "7"


def test_stat_tile_accent_tints_value(qtbot):
    tile = StatTile("CPU")
    qtbot.addWidget(tile)
    tile.set_value("90%", QColor("#ff0000"))
    assert "#ff0000" in tile._value.styleSheet()
    # Clearing the accent removes the inline colour again.
    tile.set_value("10%")
    assert tile._value.styleSheet() == ""


def test_stat_strip_creates_and_reuses_tiles_by_key(qtbot):
    strip = StatStrip()
    qtbot.addWidget(strip)
    strip.set_tile("jobs", "My jobs", "5")
    strip.set_tile("running", "Running", "2")
    assert len(strip._tiles) == 2

    # Updating an existing key reuses its tile rather than adding a new one.
    strip.set_tile("jobs", "My jobs", "8")
    assert len(strip._tiles) == 2
    assert strip._tiles["jobs"]._value.text() == "8"


def test_capacity_bar_clamps_percentage(qtbot):
    bar = CapacityBar("Memory")
    qtbot.addWidget(bar)
    bar.set_value(150, "over")
    assert bar._percentage == 100.0
    bar.set_value(-20)
    assert bar._percentage == 0.0
    bar.set_value(42.5, "ok")
    assert bar._percentage == 42.5
    assert bar._detail == "ok"
