"""Log viewer screen for slurmhub.

Displays remote log output inside the TUI using a RichLog widget,
streaming lines via paramiko instead of suspending to a shell.
"""

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Input, RichLog, Static

from slurmhub.config import LogConfig
from slurmhub.core.log_path_resolver import LogPathResolver
from slurmhub.slurm.squeue import SlurmJob
from slurmhub.slurm.ssh import SSHClient


class LogHeader(Static):
    """Header bar showing job info in the log viewer."""


class LogSearchBar(Horizontal):
    """Bottom-docked search bar shown when the user presses `/`."""


def find_match_indices(lines: list[str], query: str) -> list[int]:
    """Return the indices of lines that contain ``query`` (case-insensitive)."""
    if not query:
        return []
    q = query.lower()
    return [i for i, line in enumerate(lines) if q in line.lower()]


class LogScreen(Screen):
    """Full-screen log viewer that streams remote tail output."""

    BINDINGS = [
        Binding("escape", "close", "Back", priority=True),
        Binding("q", "close", "Back"),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("g", "scroll_home", "Top", show=False),
        Binding("G,shift+g", "scroll_end", "Bottom", show=False),
        Binding("f", "toggle_follow", "Follow"),
        Binding("slash", "toggle_search", "Search"),
        Binding("n", "next_match", "Next", show=False),
        Binding("N,shift+n", "prev_match", "Prev", show=False),
        Binding("w", "save_to_disk", "Save"),
        Binding("y", "yank_line", "Copy line"),
        Binding("question_mark", "help", "Help"),
    ]

    CSS = """
    LogHeader {
        dock: top;
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 1;
    }

    LogSearchBar {
        dock: bottom;
        height: 1;
        background: $surface;
        padding: 0 1;
    }

    LogSearchBar Input {
        height: 1;
        border: none;
        padding: 0;
        width: 1fr;
    }

    LogSearchBar Static {
        width: auto;
        padding: 0 1;
        color: $text-muted;
    }

    RichLog {
        height: 1fr;
    }
    """

    def __init__(
        self,
        job: SlurmJob,
        log_path: str,
        ssh_client: SSHClient,
        tail_lines: int = 50,
        stream: str = "stdout",
        view_command_template: str = "tail -f {log_path}",
    ):
        super().__init__()
        self.job = job
        self.log_path = log_path
        self.ssh_client = ssh_client
        self.tail_lines = tail_lines
        self.stream = stream
        self.view_command_template = view_command_template
        self._stop_stream = False
        self._follow = True
        # Plain-text mirror of what we wrote to RichLog. Used for search
        # and save-to-disk. Capped at MAX_BUFFER_LINES to bound memory
        # for long-running tail-f sessions.
        self._lines: list[str] = []
        self._match_indices: list[int] = []
        self._match_pos: int = -1  # current index into _match_indices
        self._current_match_text: Optional[str] = None

    MAX_BUFFER_LINES = 20000

    def compose(self) -> ComposeResult:
        stream_label = "stderr" if self.stream == "stderr" else "stdout"
        follow_label = "FOLLOW" if self._follow else "PAUSED"
        yield LogHeader(
            f" Job {self.job.job_id} \u2502 {stream_label} \u2502 {follow_label} \u2502 {self.log_path}",
            id="log-header",
        )
        yield RichLog(
            id="log-output",
            wrap=True,
            highlight=True,
            markup=False,
            auto_scroll=True,
        )
        with LogSearchBar(id="log-search-bar"):
            yield Input(placeholder="Search log...", id="log-search-input")
            yield Static("0 matches", id="log-search-count")
        yield Footer()

    def on_mount(self) -> None:
        # Search bar hidden by default; toggled on with `/`.
        try:
            self.query_one("#log-search-bar", LogSearchBar).display = False
        except Exception:
            pass
        self.run_worker(self._stream_log, thread=True, exclusive=True)

    def _update_header(self) -> None:
        """Refresh the header to reflect current state."""
        stream_label = "stderr" if self.stream == "stderr" else "stdout"
        follow_label = "FOLLOW" if self._follow else "PAUSED"
        try:
            header = self.query_one("#log-header", LogHeader)
            header.update(
                f" Job {self.job.job_id} \u2502 {stream_label} \u2502 {follow_label} \u2502 {self.log_path}"
            )
        except Exception:
            pass

    def _push_line(self, line: str) -> None:
        """Append a streamed line to RichLog and the plain-text mirror.

        Runs on the UI thread (called via ``call_from_thread``).
        """
        log_widget = self.query_one("#log-output", RichLog)
        log_widget.write(line)
        self._lines.append(line)
        # Cap memory growth on long sessions.
        if len(self._lines) > self.MAX_BUFFER_LINES:
            drop = len(self._lines) - self.MAX_BUFFER_LINES
            del self._lines[:drop]

    def _stream_log(self) -> None:
        """Run tail -f on the remote host and feed lines to the log widget."""

        def _on_line(text: str) -> None:
            self.app.call_from_thread(self._push_line, text)

        try:
            command = self._build_stream_command()
            self.ssh_client.stream_command(
                command,
                on_line=_on_line,
                should_stop=lambda: self._stop_stream,
            )
        except Exception as e:
            self.app.call_from_thread(self._push_line, f"\n[ERROR] {e}")

    def _build_stream_command(self) -> str:
        resolver = LogPathResolver(LogConfig(view_command=self.view_command_template))
        return resolver.render_view_command(self.log_path, tail_lines=self.tail_lines)

    def action_scroll_down(self) -> None:
        self.query_one("#log-output", RichLog).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#log-output", RichLog).scroll_up()

    def action_scroll_home(self) -> None:
        self.query_one("#log-output", RichLog).scroll_home()

    def action_scroll_end(self) -> None:
        self.query_one("#log-output", RichLog).scroll_end()

    def action_toggle_follow(self) -> None:
        """Toggle auto-scroll follow mode."""
        log_widget = self.query_one("#log-output", RichLog)
        self._follow = not self._follow
        log_widget.auto_scroll = self._follow
        self._update_header()

    def action_close(self) -> None:
        """Close the log viewer and return to the previous screen."""
        self._stop_stream = True
        self.app.pop_screen()

    def on_unmount(self) -> None:
        """Make sure the background stream thread exits with the screen."""
        self._stop_stream = True

    def action_help(self) -> None:
        from slurmhub.tui.widgets.help_screen import HelpScreen

        self.app.push_screen(HelpScreen(context="log"))

    # ── Search / save / yank ────────────────────────────────────────

    def action_toggle_search(self) -> None:
        """Show / hide the search bar."""
        try:
            bar = self.query_one("#log-search-bar", LogSearchBar)
        except Exception:
            return
        if bar.display:
            bar.display = False
            self._match_indices = []
            self._match_pos = -1
            self._current_match_text = None
        else:
            bar.display = True
            inp = self.query_one("#log-search-input", Input)
            inp.value = ""
            inp.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "log-search-input":
            return
        self._recompute_matches(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "log-search-input":
            return
        # Submit jumps to the first match (or next if pressed repeatedly).
        if self._match_indices:
            self._jump_to_match(0)
        # Hand focus back to the screen so j/k/etc. work again.
        self.set_focus(None)

    def _recompute_matches(self, query: str) -> None:
        self._match_indices = find_match_indices(self._lines, query)
        self._match_pos = -1
        self._current_match_text = None
        try:
            count = self.query_one("#log-search-count", Static)
            count.update(f"{len(self._match_indices)} matches")
        except Exception:
            pass

    def _jump_to_match(self, pos: int) -> None:
        if not self._match_indices:
            return
        pos = pos % len(self._match_indices)
        self._match_pos = pos
        line_idx = self._match_indices[pos]
        self._current_match_text = self._lines[line_idx]
        # RichLog supports scrolling to a specific y line index.
        try:
            log_widget = self.query_one("#log-output", RichLog)
            log_widget.auto_scroll = False
            self._follow = False
            self._update_header()
            log_widget.scroll_to(y=line_idx, animate=False)
        except Exception:
            pass

    def action_next_match(self) -> None:
        if not self._match_indices:
            self.notify("No matches", severity="warning", timeout=2)
            return
        self._jump_to_match(self._match_pos + 1)

    def action_prev_match(self) -> None:
        if not self._match_indices:
            self.notify("No matches", severity="warning", timeout=2)
            return
        self._jump_to_match(self._match_pos - 1)

    def _default_save_path(self) -> Path:
        downloads = Path.home() / "Downloads"
        directory = downloads if downloads.is_dir() else Path.home()
        return directory / f"{self.job.job_id}_{self.stream}.log"

    def action_save_to_disk(self) -> None:
        path = self._default_save_path()
        try:
            with path.open("w", encoding="utf-8") as fh:
                for line in self._lines:
                    fh.write(line)
                    if not line.endswith("\n"):
                        fh.write("\n")
        except OSError as e:
            self.notify(f"Save failed: {e}", severity="error", timeout=4)
            return
        self.notify(f"Saved log to {path}", timeout=3)

    def action_yank_line(self) -> None:
        from slurmhub.tui.widgets._clipboard import copy_osc52

        text = self._current_match_text
        if not text and self._lines:
            text = self._lines[-1]  # fall back to most recent line
        if not text:
            self.notify("Nothing to copy", severity="warning", timeout=2)
            return
        if copy_osc52(text):
            self.notify("Copied line to clipboard", timeout=2)
        else:
            self.notify(
                "Clipboard unavailable — line copied to notify only",
                severity="warning",
                timeout=3,
            )
