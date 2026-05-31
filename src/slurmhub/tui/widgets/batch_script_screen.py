"""Read-only viewer for the sbatch script Slurm captured at submit time.

Pushed from the job detail screen with the ``v`` key. Runs
``scontrol write batch_script <jobid> -`` over SSH and pipes the
result into a RichLog. Supports save-to-disk (``w``) and OSC 52
copy of the file path (``y``).
"""

import shlex
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, RichLog, Static
from textual.worker import WorkerState

from slurmhub.slurm.squeue import SlurmJob
from slurmhub.slurm.ssh import SSHClient


class BatchScriptHeader(Static):
    """Header row across the top of the batch script viewer."""


class BatchScriptScreen(Screen):
    """Show the submitted sbatch script for a job, read-only."""

    BINDINGS = [
        Binding("escape", "close", "Back", priority=True),
        Binding("q", "close", "Back"),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("g", "scroll_home", "Top", show=False),
        Binding("G,shift+g", "scroll_end", "Bottom", show=False),
        Binding("w", "save_to_disk", "Save"),
        Binding("y", "yank_path", "Copy path"),
    ]

    CSS = """
    BatchScriptHeader {
        dock: top;
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 1;
    }

    RichLog {
        height: 1fr;
    }
    """

    def __init__(
        self,
        job: SlurmJob,
        ssh_client: SSHClient,
        ssh_timeout: int = 10,
    ) -> None:
        super().__init__()
        self.job = job
        self.ssh_client = ssh_client
        self.ssh_timeout = ssh_timeout
        self._script_text: Optional[str] = None
        self._saved_path: Optional[Path] = None

    def compose(self) -> ComposeResult:
        yield BatchScriptHeader(
            f" Job {self.job.job_id} │ batch script │ {self.job.name}",
            id="script-header",
        )
        yield RichLog(
            id="script-output", wrap=False, highlight=False, markup=False,
            auto_scroll=False,
        )
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._fetch_script, thread=True, exclusive=True)

    def _fetch_script(self) -> str:
        quoted = shlex.quote(self.job.job_id)
        return self.ssh_client.execute(
            f"scontrol write batch_script {quoted} -",
            timeout=self.ssh_timeout,
        )

    def on_worker_state_changed(self, event) -> None:
        if event.state == WorkerState.SUCCESS:
            text = event.worker.result or ""
            self._script_text = text
            log = self.query_one("#script-output", RichLog)
            if not text.strip():
                log.write("(no script available — scontrol returned empty)")
            else:
                for line in text.splitlines():
                    log.write(line)
        elif event.state == WorkerState.ERROR:
            err = event.worker.error
            log = self.query_one("#script-output", RichLog)
            log.write(f"[ERROR] {err}")

    def _default_save_path(self) -> Path:
        downloads = Path.home() / "Downloads"
        directory = downloads if downloads.is_dir() else Path.home()
        return directory / f"{self.job.job_id}_batch.sh"

    def action_save_to_disk(self) -> None:
        text = self._script_text
        if not text:
            self.notify("Script not yet loaded", severity="warning", timeout=2)
            return
        path = self._default_save_path()
        try:
            path.write_text(text, encoding="utf-8")
        except OSError as e:
            self.notify(f"Save failed: {e}", severity="error", timeout=4)
            return
        self._saved_path = path
        self.notify(f"Saved script to {path}", timeout=3)

    def action_yank_path(self) -> None:
        from slurmhub.tui.widgets._clipboard import copy_osc52

        path = self._saved_path or self._default_save_path()
        path_str = str(path)
        if copy_osc52(path_str):
            self.notify(f"Copied path: {path_str}", timeout=2)
        else:
            self.notify(
                f"Clipboard unavailable — {path_str}",
                severity="warning",
                timeout=3,
            )

    def action_close(self) -> None:
        self.app.pop_screen()

    def action_scroll_down(self) -> None:
        self.query_one("#script-output", RichLog).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#script-output", RichLog).scroll_up()

    def action_scroll_home(self) -> None:
        self.query_one("#script-output", RichLog).scroll_home()

    def action_scroll_end(self) -> None:
        self.query_one("#script-output", RichLog).scroll_end()
