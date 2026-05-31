"""Generate PySide6 GUI screenshots for the docs (offscreen, demo data).

Run with the offscreen platform so it needs no display:

    QT_QPA_PLATFORM=offscreen uv run python docs/scripts/generate_gui_screenshots.py

Writes PNGs to ``docs/_static/screenshots/``. The Textual SVG screenshots are
still produced by ``generate_screenshots.py`` for the ``--tui`` docs.
"""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from slurmhub.config import AppConfig, ProfileConfig, SSHConfig  # noqa: E402
from slurmhub.db import open_demo_database  # noqa: E402
from slurmhub.demo_data import DEMO_HOST, DEMO_USERNAME  # noqa: E402
from slurmhub.qt.controller import AppController  # noqa: E402
from slurmhub.qt.main_window import MainWindow  # noqa: E402
from slurmhub.qt.theme import apply_theme  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "_static" / "screenshots"


def _settle(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])

    for mode in ("light", "dark"):
        apply_theme(app, mode)
        config = AppConfig(
            profiles={
                "demo": ProfileConfig(
                    name="demo", ssh=SSHConfig(host=DEMO_HOST, username=DEMO_USERNAME)
                )
            }
        )
        controller = AppController(config, demo=True, database=open_demo_database())
        window = MainWindow(controller)
        window.resize(1200, 760)
        window.show()
        controller.start()
        _settle(1500)

        window.queue_view.reload()
        window.grab().save(str(OUT / f"gui-queue-{mode}.png"))

        window.nav_list.setCurrentRow(1)  # Cluster
        _settle(300)
        window.grab().save(str(OUT / f"gui-cluster-{mode}.png"))

        controller.shutdown()
        window.deleteLater()
        _settle(50)

    print(f"Wrote GUI screenshots to {OUT}")


if __name__ == "__main__":
    main()
