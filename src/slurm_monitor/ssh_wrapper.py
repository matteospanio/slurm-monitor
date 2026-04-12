"""SSH wrapper using paramiko for executing remote commands on Slurm clusters."""

import os
import socket
from typing import Optional

import paramiko

from slurm_monitor.config import SSHConfig


class SSHConnectionError(Exception):
    """Raised when SSH connection fails."""


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

    @property
    def host(self) -> str:
        """Return the configured host."""
        return self.config.host

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
            raise SSHConnectionError(
                f"SSH authentication to {self.config.host} failed: {e}"
            ) from e
        except (paramiko.SSHException, OSError) as e:
            self.close()
            raise SSHConnectionError(
                f"SSH connection to {self.config.host} failed: {e}"
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
        kwargs: dict = {
            "hostname": hostname,
            "port": self.config.port,
            "timeout": timeout,
            "allow_agent": True,
            "look_for_keys": True,
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

        if self.config.passphrase:
            kwargs["passphrase"] = self.config.passphrase

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
