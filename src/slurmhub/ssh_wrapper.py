"""SSH wrapper using paramiko for executing remote commands on Slurm clusters."""

import os
import socket
import time
from typing import Callable, Optional

import paramiko

from slurmhub.config import SSHConfig


class SSHConnectionError(Exception):
    """Raised when SSH connection fails."""


class SSHAuthenticationError(SSHConnectionError):
    """Raised when SSH authentication fails (wrong/missing credentials)."""


class SSHTimeoutError(Exception):
    """Raised when SSH command times out."""


class SSHClient:
    """Persistent SSH client wrapping paramiko.

    Maintains an open connection for reuse across multiple commands.
    Supports key auth, password auth, jump hosts, and custom ports.
    """

    def __init__(self, config: SSHConfig):
        """Initialize the SSH client.

        Args:
            config: SSH connection configuration
        """
        self.config = config
        self._client: Optional[paramiko.SSHClient] = None
        self._jump_client: Optional[paramiko.SSHClient] = None
        self._jump_channel = None
        self._runtime_password: Optional[str] = None
        self._runtime_passphrase: Optional[str] = None

    @property
    def host(self) -> str:
        """Return the configured host."""
        return self.config.host

    def set_credentials(
        self,
        password: Optional[str] = None,
        passphrase: Optional[str] = None,
    ) -> None:
        """Set runtime credentials for authentication.

        Closes any existing connection so the next call reconnects
        with the new credentials. Credentials are held in memory only.

        Args:
            password: SSH password for password-based authentication
            passphrase: Passphrase for encrypted SSH keys
        """
        self._runtime_password = password
        self._runtime_passphrase = passphrase
        self.close()

    def connect(self, timeout: int = 10) -> None:
        """Establish SSH connection.

        Args:
            timeout: Connection timeout in seconds

        Raises:
            SSHConnectionError: If connection fails
            SSHTimeoutError: If connection times out
        """
        if self._client is not None:
            try:
                self._client.get_transport().send_ignore()
                return  # already connected and alive
            except Exception:
                self.close()

        try:
            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = self._build_connect_kwargs(timeout)

            if self.config.jump_host:
                self._connect_via_jump(connect_kwargs, timeout)
            else:
                self._client.connect(**connect_kwargs)

        except socket.timeout as e:
            self.close()
            raise SSHTimeoutError(
                f"SSH connection to {self.config.host} timed out "
                f"after {timeout} seconds"
            ) from e
        except paramiko.AuthenticationException as e:
            self.close()
            raise SSHAuthenticationError(
                f"SSH authentication to {self.config.host} failed: {e}"
            ) from e
        except (paramiko.SSHException, OSError) as e:
            self.close()
            # "No existing session" occurs when the SSH agent is
            # unavailable — providing a password can resolve it.
            msg = str(e).lower()
            if "no existing session" in msg or "authentication" in msg:
                raise SSHAuthenticationError(
                    f"SSH connection to {self.config.host} failed: {e}"
                ) from e
            raise SSHConnectionError(
                f"SSH connection to {self.config.host} failed: {e}"
            ) from e
        except AttributeError as e:
            # Paramiko bug: when agent keys exhaust MaxAuthTries the
            # transport dies, then paramiko tries to log through the
            # dead transport and raises AttributeError.  Treat as auth
            # failure so the password prompt can recover.
            self.close()
            raise SSHAuthenticationError(
                f"SSH authentication to {self.config.host} failed: "
                f"too many agent keys rejected by server"
            ) from e

    def _build_connect_kwargs(self, timeout: int) -> dict:
        """Build keyword arguments for paramiko connect().

        Reads ~/.ssh/config to resolve host aliases, real hostnames,
        usernames, ports, identity files, and proxy commands — then
        lets explicit SSHConfig fields override.
        """
        ssh_config_path = os.path.expanduser("~/.ssh/config")
        host_cfg: dict = {}
        if os.path.exists(ssh_config_path):
            cfg = paramiko.SSHConfig()
            with open(ssh_config_path) as f:
                cfg.parse(f)
            host_cfg = cfg.lookup(self.config.host)

        # Start with the resolved hostname (or the original alias)
        hostname = host_cfg.get("hostname", self.config.host)
        # When runtime credentials are provided, skip the SSH agent to
        # avoid exhausting MaxAuthTries with unrelated agent keys before
        # the password/passphrase is even attempted.
        has_runtime_creds = bool(
            self._runtime_password or self._runtime_passphrase
        )
        kwargs: dict = {
            "hostname": hostname,
            "port": self.config.port,
            "timeout": timeout,
            "allow_agent": not has_runtime_creds,
            "look_for_keys": not has_runtime_creds,
        }

        # Apply SSH config values as defaults, let explicit config override
        if self.config.username:
            kwargs["username"] = self.config.username
        elif "user" in host_cfg:
            kwargs["username"] = host_cfg["user"]

        if self.config.key_filename:
            kwargs["key_filename"] = self.config.key_filename
        elif "identityfile" in host_cfg:
            kwargs["key_filename"] = [
                os.path.expanduser(k) for k in host_cfg["identityfile"]
            ]

        if self.config.port != 22:
            kwargs["port"] = self.config.port
        elif "port" in host_cfg:
            kwargs["port"] = int(host_cfg["port"])

        if self._runtime_passphrase:
            kwargs["passphrase"] = self._runtime_passphrase
        elif self.config.passphrase:
            kwargs["passphrase"] = self.config.passphrase

        if self._runtime_password:
            kwargs["password"] = self._runtime_password

        # ProxyCommand support from SSH config
        if not self.config.jump_host and "proxycommand" in host_cfg:
            kwargs["sock"] = paramiko.ProxyCommand(host_cfg["proxycommand"])

        return kwargs

    def _connect_via_jump(self, connect_kwargs: dict, timeout: int) -> None:
        """Connect through a jump/bastion host."""
        self._jump_client = paramiko.SSHClient()
        self._jump_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        jump_kwargs: dict = {
            "hostname": self.config.jump_host,
            "port": 22,
            "timeout": timeout,
            "allow_agent": True,
            "look_for_keys": True,
        }
        if self.config.username:
            jump_kwargs["username"] = self.config.username
        if self._runtime_password:
            jump_kwargs["password"] = self._runtime_password
        if self._runtime_passphrase:
            jump_kwargs["passphrase"] = self._runtime_passphrase

        self._jump_client.connect(**jump_kwargs)

        jump_transport = self._jump_client.get_transport()
        self._jump_channel = jump_transport.open_channel(
            "direct-tcpip",
            (self.config.host, self.config.port),
            ("127.0.0.1", 0),
        )

        connect_kwargs["sock"] = self._jump_channel
        self._client.connect(**connect_kwargs)

    def execute(self, command: str, timeout: int = 10) -> str:
        """Execute a command on the remote host.

        Args:
            command: The command to execute
            timeout: Command execution timeout in seconds

        Returns:
            stdout from the remote command

        Raises:
            SSHConnectionError: If not connected or connection lost
            SSHTimeoutError: If command times out
        """
        self.connect(timeout)

        try:
            _, stdout, stderr = self._client.exec_command(
                command, timeout=timeout
            )
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8").strip()

            if exit_status != 0:
                error_output = stderr.read().decode("utf-8").strip()
                raise SSHConnectionError(
                    f"Command failed on {self.config.host} "
                    f"(exit {exit_status}): {error_output or command}"
                )

            return output

        except socket.timeout as e:
            raise SSHTimeoutError(
                f"SSH command to {self.config.host} timed out "
                f"after {timeout} seconds"
            ) from e
        except SSHConnectionError:
            raise
        except SSHTimeoutError:
            raise
        except (paramiko.SSHException, OSError) as e:
            self.close()
            raise SSHConnectionError(
                f"SSH command to {self.config.host} failed: {e}"
            ) from e

    def stream_command(
        self,
        command: str,
        on_line: Callable[[str], None],
        should_stop: Callable[[], bool] = lambda: False,
        timeout: int = 10,
        poll_interval: float = 0.1,
    ) -> None:
        """Run a long-running command on the remote host and stream its output.

        ``on_line`` is called once per newline-terminated chunk read from
        stdout. ``should_stop`` is polled between reads so the caller can
        request early termination (e.g. screen closing). The method blocks
        until the channel closes, ``should_stop`` returns ``True``, or an
        error occurs.
        """
        self.connect(timeout)
        transport = self._client.get_transport()
        channel = transport.open_session()
        try:
            channel.exec_command(command)
            buf = b""
            while not channel.exit_status_ready():
                if should_stop():
                    break
                if channel.recv_ready():
                    data = channel.recv(4096)
                    if not data:
                        break
                    buf += data
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        on_line(line.decode("utf-8", errors="replace"))
                else:
                    time.sleep(poll_interval)
            if buf:
                on_line(buf.decode("utf-8", errors="replace"))
        finally:
            try:
                channel.close()
            except Exception:
                pass

    def check_connection(self, timeout: int = 10) -> bool:
        """Check if SSH connection to host is working.

        Args:
            timeout: Timeout in seconds for the connection test

        Returns:
            True if connection successful, False otherwise
        """
        try:
            result = self.execute('echo "success"', timeout)
            return result == "success"
        except (SSHConnectionError, SSHTimeoutError):
            return False

    def close(self) -> None:
        """Close the SSH connection and clean up resources."""
        if self._jump_channel is not None:
            try:
                self._jump_channel.close()
            except Exception:
                pass
            self._jump_channel = None

        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

        if self._jump_client is not None:
            try:
                self._jump_client.close()
            except Exception:
                pass
            self._jump_client = None

    def __del__(self) -> None:
        self.close()

    def __enter__(self) -> "SSHClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()


class DemoSSHClient(SSHClient):
    """Drop-in SSHClient replacement backed by static fixture data.

    Used by the ``--demo`` CLI flag so the TUI can be exercised (and the
    documentation screenshots regenerated) without a live Slurm cluster.
    Every command the app issues is matched by prefix and answered from
    :mod:`slurmhub.demo_data`.
    """

    def __init__(self, config: Optional[SSHConfig] = None):
        if config is None:
            from slurmhub.demo_data import DEMO_HOST, DEMO_USERNAME
            config = SSHConfig(host=DEMO_HOST, username=DEMO_USERNAME)
        super().__init__(config)

    def connect(self, timeout: int = 10) -> None:  # noqa: D401 — interface compat
        # No real connection is made in demo mode.
        return None

    def close(self) -> None:
        return None

    def set_credentials(
        self,
        password: Optional[str] = None,
        passphrase: Optional[str] = None,
    ) -> None:
        # Credentials are irrelevant in demo mode.
        return None

    def check_connection(self, timeout: int = 10) -> bool:
        return True

    def execute(self, command: str, timeout: int = 10) -> str:
        from slurmhub import demo_data

        cmd = command.strip()

        # squeue --me with format string (active jobs)
        if cmd.startswith("squeue --me -o "):
            return demo_data.SQUEUE_OUTPUT

        # squeue --me -t PENDING -o "..." (pending details)
        if cmd.startswith("squeue --me -t PENDING"):
            return demo_data.SQUEUE_PENDING_DETAILS

        # squeue -t PENDING ... --sort=-Q (queue ranks)
        if cmd.startswith("squeue -t PENDING"):
            return demo_data.SQUEUE_QUEUE_RANKS

        # squeue --noheader -o "%T" (cluster-wide state counts)
        if cmd.startswith('squeue --noheader -o "%T"'):
            return demo_data.SQUEUE_CLUSTER_STATES

        # sacct historical jobs
        if cmd.startswith("sacct "):
            return demo_data.SACCT_OUTPUT

        # sinfo per-node (-N flag)
        if cmd.startswith("sinfo ") and " -N " in cmd:
            return demo_data.SINFO_NODES

        # sinfo per-partition
        if cmd.startswith("sinfo "):
            return demo_data.SINFO_PARTITIONS

        # scontrol show job <id>
        if cmd.startswith("scontrol show job "):
            job_id = cmd.split()[-1].strip()
            return demo_data.SCONTROL_JOBS.get(job_id, "")

        # scontrol write batch_script <id> -
        if cmd.startswith("scontrol write batch_script "):
            parts = cmd.split()
            if len(parts) >= 4:
                return demo_data.get_batch_script(parts[3])
            return demo_data.DEFAULT_BATCH_SCRIPT

        # sstat memory usage for a running job
        if cmd.startswith("sstat "):
            for jid, out in demo_data.SSTAT_OUTPUTS.items():
                if f"-j {jid}" in cmd:
                    return out
            return ""

        # srun ... nvidia-smi (GPU stats for a running job)
        if "nvidia-smi" in cmd:
            for jid, out in demo_data.NVIDIA_SMI_OUTPUTS.items():
                if f"--jobid={jid}" in cmd:
                    return out
            return ""

        # scancel <id> — no-op in demo mode but report success
        if cmd.startswith("scancel "):
            return ""

        # echo "success" — used by check_connection
        if cmd.startswith("echo "):
            return cmd.split(None, 1)[1].strip().strip('"')

        return ""

    def stream_command(
        self,
        command: str,
        on_line: Callable[[str], None],
        should_stop: Callable[[], bool] = lambda: False,
        timeout: int = 10,
        poll_interval: float = 0.1,
    ) -> None:
        """Replay canned log content for ``tail -f <path>`` commands."""
        from slurmhub import demo_data

        cmd = command.strip()
        # Expected form: ``tail -n 50 -f /path/to/log``
        path = ""
        if "-f " in cmd:
            path = cmd.split("-f ", 1)[1].strip()
        content = demo_data.get_log_content(path)
        for line in content.splitlines():
            if should_stop():
                return
            on_line(line)
        # Hold the "stream" open until the caller asks us to stop,
        # mimicking the behavior of ``tail -f`` on a live cluster so
        # the LogScreen header stays in FOLLOW mode.
        while not should_stop():
            time.sleep(poll_interval)
