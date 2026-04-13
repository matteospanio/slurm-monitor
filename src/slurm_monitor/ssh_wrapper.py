"""SSH wrapper using paramiko for executing remote commands on Slurm clusters."""

import os
import socket
from typing import Optional

import paramiko

from slurm_monitor.config import SSHConfig


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
