"""First-run setup wizard.

A modal Textual screen that collects enough SSH + log settings to build a
single :class:`ProfileConfig`. It's launched by :func:`cli.main` when no
config file is found anywhere in the default search path. See plan.md
"Epic 14" for context.
"""

import getpass
import os
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from slurmhub.config import LogConfig, ProfileConfig, SSHConfig
from slurmhub.slurm.ssh import (
    SSHAuthenticationError,
    SSHClient,
    SSHConnectionError,
    SSHTimeoutError,
)


def _default_key_path() -> str:
    """Return ``~/.ssh/id_ed25519`` if it exists, else ``~/.ssh/id_rsa``."""
    home = Path.home()
    ed = home / ".ssh" / "id_ed25519"
    rsa = home / ".ssh" / "id_rsa"
    if ed.exists():
        return str(ed)
    return str(rsa)


def build_profile_from_fields(
    name: str,
    host: str,
    username: str,
    port: str,
    key_filename: str,
    log_pattern: str,
) -> tuple[Optional[ProfileConfig], Optional[str]]:
    """Validate wizard form fields and build a ProfileConfig.

    Returns ``(profile, error_message)``. On success ``error_message`` is
    None; on validation failure ``profile`` is None and ``error_message``
    holds a user-facing explanation.
    """
    name = name.strip() or "default"
    host = host.strip()
    if not host:
        return None, "SSH host is required."

    try:
        port_int = int(port.strip() or "22")
    except ValueError:
        return None, "SSH port must be a number."

    expanded_key = os.path.expanduser(key_filename.strip()) if key_filename.strip() else ""
    expanded_pattern = log_pattern.strip() or "{work_dir}/logs/{job_id}.out"

    profile = ProfileConfig(
        name=name,
        ssh=SSHConfig(
            host=host,
            port=port_int,
            username=username.strip(),
            key_filename=expanded_key,
        ),
        log=LogConfig(default_pattern=expanded_pattern),
    )
    return profile, None


class FirstRunWizardScreen(ModalScreen[Optional[ProfileConfig]]):
    """Modal that collects a single cluster profile from the user."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    FirstRunWizardScreen {
        align: center middle;
        background: $background 60%;
    }

    FirstRunWizardScreen #wizard-dialog {
        width: 80%;
        min-width: 60;
        max-width: 100;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    FirstRunWizardScreen #wizard-title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }

    FirstRunWizardScreen #wizard-hint {
        width: 100%;
        color: $text-muted;
        margin-bottom: 1;
    }

    FirstRunWizardScreen .wizard-row {
        height: 3;
        margin-bottom: 0;
    }

    FirstRunWizardScreen .wizard-label {
        width: 18;
        content-align: right middle;
        padding-right: 1;
    }

    FirstRunWizardScreen .wizard-input {
        width: 1fr;
    }

    FirstRunWizardScreen #wizard-status {
        width: 100%;
        margin: 1 0;
        min-height: 1;
    }

    FirstRunWizardScreen #wizard-buttons {
        height: auto;
        align-horizontal: center;
        margin-top: 1;
    }

    FirstRunWizardScreen Button {
        margin: 0 1;
    }
    """

    def __init__(self, default_name: str = "default") -> None:
        super().__init__()
        self.default_name = default_name

    # ── Composition ─────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Vertical(id="wizard-dialog"):
            yield Static("slurmhub — First-run setup", id="wizard-title")
            yield Static(
                "No config found. Fill in your cluster details below. "
                "Press [bold]Test connection[/bold] to verify, then "
                "[bold]Save[/bold] to continue.",
                id="wizard-hint",
            )

            with Horizontal(classes="wizard-row"):
                yield Label("Profile name", classes="wizard-label")
                yield Input(value=self.default_name, id="field-name", classes="wizard-input")
            with Horizontal(classes="wizard-row"):
                yield Label("SSH host", classes="wizard-label")
                yield Input(placeholder="login.cluster.example.org", id="field-host", classes="wizard-input")
            with Horizontal(classes="wizard-row"):
                yield Label("Username", classes="wizard-label")
                yield Input(value=getpass.getuser(), id="field-username", classes="wizard-input")
            with Horizontal(classes="wizard-row"):
                yield Label("Port", classes="wizard-label")
                yield Input(value="22", id="field-port", classes="wizard-input")
            with Horizontal(classes="wizard-row"):
                yield Label("SSH key path", classes="wizard-label")
                yield Input(value=_default_key_path(), id="field-key", classes="wizard-input")
            with Horizontal(classes="wizard-row"):
                yield Label("Log path pattern", classes="wizard-label")
                yield Input(
                    value="{work_dir}/logs/{job_id}.out",
                    id="field-log",
                    classes="wizard-input",
                )

            yield Static("", id="wizard-status")

            with Horizontal(id="wizard-buttons"):
                yield Button("Test connection", id="btn-test", variant="primary")
                yield Button("Save and continue", id="btn-save", variant="success")
                yield Button("Cancel", id="btn-cancel", variant="error")

    # ── Helpers ─────────────────────────────────────────────────────────

    def _collect(self) -> tuple[Optional[ProfileConfig], Optional[str]]:
        return build_profile_from_fields(
            name=self.query_one("#field-name", Input).value,
            host=self.query_one("#field-host", Input).value,
            username=self.query_one("#field-username", Input).value,
            port=self.query_one("#field-port", Input).value,
            key_filename=self.query_one("#field-key", Input).value,
            log_pattern=self.query_one("#field-log", Input).value,
        )

    def _set_status(self, message: str, style: str = "") -> None:
        status = self.query_one("#wizard-status", Static)
        if style:
            status.update(f"[{style}]{message}[/{style}]")
        else:
            status.update(message)

    # ── Button handlers ─────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self._on_save()
        elif event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-test":
            self._on_test()

    def _on_save(self) -> None:
        profile, err = self._collect()
        if err is not None:
            self._set_status(err, style="red")
            return
        self.dismiss(profile)

    def _on_test(self) -> None:
        profile, err = self._collect()
        if err is not None:
            self._set_status(err, style="red")
            return
        assert profile is not None
        self._set_status("Connecting…", style="dim italic")
        # Run the SSH probe on a worker thread so the UI stays responsive.
        self.run_worker(
            lambda p=profile: self._probe(p),
            thread=True,
            exclusive=True,
            name="wizard-probe",
        )

    @staticmethod
    def _probe(profile: ProfileConfig) -> tuple[bool, str]:
        client = SSHClient(profile.ssh)
        try:
            ok = client.check_connection(timeout=10)
            return (ok, "" if ok else "Connection failed.")
        except SSHAuthenticationError as e:
            return (False, f"Authentication failed: {e}")
        except SSHTimeoutError as e:
            return (False, f"Timed out: {e}")
        except SSHConnectionError as e:
            return (False, f"Connection error: {e}")
        except Exception as e:  # noqa: BLE001 — surface unexpected errors
            return (False, f"{type(e).__name__}: {e}")
        finally:
            try:
                client.close()
            except Exception:
                pass

    def on_worker_state_changed(self, event) -> None:
        from textual.worker import WorkerState

        if event.worker.name != "wizard-probe":
            return
        if event.state == WorkerState.SUCCESS:
            ok, msg = event.worker.result
            if ok:
                self._set_status("✓ Connection succeeded.", style="green")
            else:
                self._set_status(f"✗ {msg}", style="red")
        elif event.state == WorkerState.ERROR:
            self._set_status(f"✗ {event.worker.error}", style="red")

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    """Small Y/N modal used to ask 'Add another cluster?' after each save."""

    BINDINGS = [
        Binding("escape", "no", "No"),
        Binding("n", "no", "No"),
        Binding("y", "yes", "Yes"),
    ]

    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
        background: $background 60%;
    }

    ConfirmScreen #confirm-dialog {
        width: 60%;
        min-width: 40;
        max-width: 80;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    ConfirmScreen #confirm-prompt {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }

    ConfirmScreen #confirm-buttons {
        height: auto;
        align-horizontal: center;
    }
    """

    def __init__(self, prompt: str) -> None:
        super().__init__()
        self.prompt = prompt

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Static(self.prompt, id="confirm-prompt")
            with Horizontal(id="confirm-buttons"):
                yield Button("Yes (y)", id="btn-yes", variant="success")
                yield Button("No (n)", id="btn-no", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-yes":
            self.dismiss(True)
        elif event.button.id == "btn-no":
            self.dismiss(False)

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)
