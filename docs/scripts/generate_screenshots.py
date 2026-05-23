"""Generate SVG screenshots of the TUI for the documentation site.

Each screenshot drives the app in demo mode via a Textual Pilot, navigates
to the target screen with key events, waits for it to settle, then calls
``App.save_screenshot()``. The SVGs land in ``docs/_static/screenshots/``.

Run from the repo root:

    uv run python docs/scripts/generate_screenshots.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from slurmhub.app import SlurmhubApp
from slurmhub.config import AppConfig, ProfileConfig, SSHConfig
from slurmhub.demo_data import DEMO_HOST, DEMO_USERNAME

OUT_DIR = Path(__file__).resolve().parents[1] / "_static" / "screenshots"
TERMINAL_SIZE = (120, 36)


def _demo_config() -> AppConfig:
    profile = ProfileConfig(
        name="demo",
        ssh=SSHConfig(host=DEMO_HOST, username=DEMO_USERNAME),
    )
    return AppConfig(profiles={"demo": profile})


def _new_app() -> SlurmhubApp:
    return SlurmhubApp(config=_demo_config(), demo=True)


async def _wait_until_jobs_loaded(app: SlurmhubApp, pilot) -> None:
    """Wait for the demo refresh worker to finish populating the table."""
    tab = app._profile_tabs["demo"]
    for _ in range(40):  # up to ~2 seconds
        await pilot.pause(0.05)
        if tab.jobs:
            await pilot.pause(0.1)  # let one more update-display tick run
            return


async def _shot(app: SlurmhubApp, pilot, filename: str) -> None:
    target = OUT_DIR / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    app.save_screenshot(path=str(OUT_DIR), filename=filename)
    if not target.exists():
        raise RuntimeError(f"save_screenshot didn't produce {target}")


async def shot_main_job_table() -> None:
    app = _new_app()
    async with app.run_test(size=TERMINAL_SIZE) as pilot:
        await _wait_until_jobs_loaded(app, pilot)
        await _shot(app, pilot, "01_main_job_table.svg")


async def shot_job_detail() -> None:
    app = _new_app()
    async with app.run_test(size=TERMINAL_SIZE) as pilot:
        await _wait_until_jobs_loaded(app, pilot)
        await pilot.press("enter")
        await pilot.pause(0.5)
        await _shot(app, pilot, "02_job_detail.svg")


async def shot_log_viewer() -> None:
    app = _new_app()
    async with app.run_test(size=TERMINAL_SIZE) as pilot:
        await _wait_until_jobs_loaded(app, pilot)
        await pilot.press("enter")  # → detail screen
        await pilot.pause(0.4)
        await pilot.press("o")      # → log viewer (stdout)
        await pilot.pause(0.4)      # let the demo stream replay
        await _shot(app, pilot, "03_log_viewer.svg")


async def shot_log_viewer_search() -> None:
    app = _new_app()
    async with app.run_test(size=TERMINAL_SIZE) as pilot:
        await _wait_until_jobs_loaded(app, pilot)
        await pilot.press("enter")
        await pilot.pause(0.4)
        await pilot.press("o")
        await pilot.pause(0.4)
        await pilot.press("slash")  # open search bar
        await pilot.pause(0.1)
        # Type a query that will have hits in the demo log fixture.
        for ch in "Epoch":
            await pilot.press(ch)
        await pilot.pause(0.2)
        await _shot(app, pilot, "04_log_viewer_search.svg")


async def shot_cluster_dashboard() -> None:
    app = _new_app()
    async with app.run_test(size=TERMINAL_SIZE) as pilot:
        await _wait_until_jobs_loaded(app, pilot)
        await pilot.press("d")
        await pilot.pause(0.5)
        await _shot(app, pilot, "05_cluster_dashboard.svg")


async def shot_help_screen() -> None:
    app = _new_app()
    async with app.run_test(size=TERMINAL_SIZE) as pilot:
        await _wait_until_jobs_loaded(app, pilot)
        await pilot.press("question_mark")
        await pilot.pause(0.3)
        await _shot(app, pilot, "06_help_screen.svg")


async def shot_first_run_wizard() -> None:
    """Render the wizard as a stand-alone modal — same code path as on first run."""
    from textual.app import App, ComposeResult
    from slurmhub.widgets.first_run_wizard import FirstRunWizardScreen

    class WizardHost(App):
        CSS = ""

        def compose(self) -> ComposeResult:
            return []

        def on_mount(self) -> None:
            self.push_screen(FirstRunWizardScreen(default_name="default"))

    host = WizardHost()
    async with host.run_test(size=TERMINAL_SIZE) as pilot:
        await pilot.pause(0.3)
        target = OUT_DIR / "07_first_run_wizard.svg"
        host.save_screenshot(path=str(OUT_DIR), filename=target.name)


async def shot_batch_script() -> None:
    app = _new_app()
    async with app.run_test(size=TERMINAL_SIZE) as pilot:
        await _wait_until_jobs_loaded(app, pilot)
        await pilot.press("enter")
        await pilot.pause(0.4)
        await pilot.press("v")  # batch script viewer
        await pilot.pause(0.4)
        await _shot(app, pilot, "08_batch_script.svg")


async def shot_confirm_scancel() -> None:
    app = _new_app()
    async with app.run_test(size=TERMINAL_SIZE) as pilot:
        await _wait_until_jobs_loaded(app, pilot)
        await pilot.press("c")  # confirm modal for scancel
        await pilot.pause(0.3)
        await _shot(app, pilot, "09_confirm_scancel.svg")


SHOTS = [
    shot_main_job_table,
    shot_job_detail,
    shot_log_viewer,
    shot_log_viewer_search,
    shot_cluster_dashboard,
    shot_help_screen,
    shot_first_run_wizard,
    shot_batch_script,
    shot_confirm_scancel,
]


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for shot in SHOTS:
        print(f"  → {shot.__name__}")
        await shot()
    print(f"\nWrote {len(SHOTS)} screenshots to {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
