"""Log viewer screen for Slurm Monitor.

Displays remote log output inside the TUI using a RichLog widget,
streaming lines via paramiko instead of suspending to a shell.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, RichLog, Static

from slurm_monitor.squeue_parser import SlurmJob
from slurm_monitor.ssh_wrapper import SSHClient


class LogHeader(Static):
    """Header bar showing job info in the log viewer."""


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
    ]

    CSS = """
    LogHeader {
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
        log_path: str,
        ssh_client: SSHClient,
        tail_lines: int = 50,
        stream: str = "stdout",
    ):
        super().__init__()
        self.job = job
        self.log_path = log_path
        self.ssh_client = ssh_client
        self.tail_lines = tail_lines
        self.stream = stream
        self._channel = None
        self._follow = True

    def compose(self) -> ComposeResult:
        stream_label = "stderr" if self.stream == "stderr" else "stdout"
        follow_label = "FOLLOW" if self._follow else "PAUSED"
        yield LogHeader(
            f" Job {self.job.job_id} \u2502 {stream_label} \u2502 {follow_label} \u2502 {self.log_path}",
            id="log-header",
        )
        yield RichLog(
            id="log-output", wrap=True, highlight=True, markup=False,
            auto_scroll=True,
        )
        yield Footer()

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

    def on_mount(self) -> None:
        self.run_worker(self._stream_log, thread=True, exclusive=True)

    def _stream_log(self) -> None:
        """Run tail -f on the remote host and feed lines to the log widget."""
        log_widget = self.query_one("#log-output", RichLog)

        try:
            self.ssh_client.connect(timeout=10)
            transport = self.ssh_client._client.get_transport()
            self._channel = transport.open_session()
            self._channel.exec_command(f"tail -n {self.tail_lines} -f {self.log_path}")

            buf = b""
            while not self._channel.exit_status_ready():
                if self._channel.recv_ready():
                    data = self._channel.recv(4096)
                    if not data:
                        break
                    buf += data
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        self.app.call_from_thread(
                            log_widget.write, line.decode("utf-8", errors="replace")
                        )
                else:
                    import time
                    time.sleep(0.1)

            # Flush remaining buffer
            if buf:
                self.app.call_from_thread(
                    log_widget.write, buf.decode("utf-8", errors="replace")
                )

        except Exception as e:
            self.app.call_from_thread(log_widget.write, f"\n[ERROR] {e}")

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
        if self._channel is not None:
            try:
                self._channel.close()
            except Exception:
                pass
            self._channel = None
        self.app.pop_screen()
