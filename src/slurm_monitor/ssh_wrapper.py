"""SSH wrapper for executing remote commands on Slurm clusters."""

import subprocess
from typing import Optional


class SSHConnectionError(Exception):
    """Raised when SSH connection fails."""

    pass


class SSHTimeoutError(Exception):
    """Raised when SSH command times out."""

    pass


def execute_ssh_command(
    host: str,
    command: str = 'echo "success"',
    timeout: int = 10,
) -> str:
    """
    Execute a command on a remote host via SSH.

    Args:
        host: The remote host to connect to
        command: The command to execute on the remote host
        timeout: Timeout in seconds for the SSH connection

    Returns:
        The stdout from the remote command

    Raises:
        SSHConnectionError: If the SSH connection fails
        SSHTimeoutError: If the command times out
    """
    ssh_command = ["ssh", host, command]

    try:
        result = subprocess.run(
            ssh_command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
        return result.stdout.strip()

    except subprocess.TimeoutExpired as e:
        raise SSHTimeoutError(
            f"SSH command to {host} timed out after {timeout} seconds"
        ) from e

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        raise SSHConnectionError(
            f"SSH connection to {host} failed: {error_msg}"
        ) from e

    except FileNotFoundError as e:
        raise SSHConnectionError(
            "SSH client not found. Please ensure SSH is installed."
        ) from e


def check_connection(host: str, timeout: int = 10) -> bool:
    """
    Check if SSH connection to host is working.

    Args:
        host: The remote host to check connection to
        timeout: Timeout in seconds for the connection test

    Returns:
        True if connection successful, False otherwise
    """
    try:
        result = execute_ssh_command(host, 'echo "success"', timeout)
        return result == "success"
    except (SSHConnectionError, SSHTimeoutError):
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m slurm_monitor.ssh_wrapper <host> [command]")
        sys.exit(1)

    host = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else 'echo "success"'

    try:
        output = execute_ssh_command(host, command)
        print(output)
        sys.exit(0)
    except SSHTimeoutError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    except SSHConnectionError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(3)
