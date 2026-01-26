"""Tests for SSH wrapper functionality."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from slurm_monitor.ssh_wrapper import (
    SSHConnectionError,
    SSHTimeoutError,
    check_connection,
    execute_ssh_command,
)


class TestExecuteSSHCommand:
    """Test suite for execute_ssh_command function."""

    def test_successful_connection(self):
        """Test successful SSH connection returns expected output."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="success\n", stderr="", returncode=0
            )

            result = execute_ssh_command("testhost")

            assert result == "success"
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args == ["ssh", "testhost", 'echo "success"']

    def test_custom_command(self):
        """Test executing custom command via SSH."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="custom output\n", stderr="", returncode=0
            )

            result = execute_ssh_command("testhost", "ls -la")

            assert result == "custom output"
            args = mock_run.call_args[0][0]
            assert args == ["ssh", "testhost", "ls -la"]

    def test_timeout_raises_error(self):
        """Test that timeout raises SSHTimeoutError."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["ssh", "testhost"], timeout=10
            )

            with pytest.raises(SSHTimeoutError) as exc_info:
                execute_ssh_command("testhost", timeout=10)

            assert "timed out after 10 seconds" in str(exc_info.value)

    def test_connection_error_raises_error(self):
        """Test that connection errors raise SSHConnectionError."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=255,
                cmd=["ssh", "testhost"],
                stderr="Connection refused",
            )

            with pytest.raises(SSHConnectionError) as exc_info:
                execute_ssh_command("testhost")

            assert "SSH connection to testhost failed" in str(exc_info.value)

    def test_ssh_not_installed(self):
        """Test handling when SSH client is not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("ssh command not found")

            with pytest.raises(SSHConnectionError) as exc_info:
                execute_ssh_command("testhost")

            assert "SSH client not found" in str(exc_info.value)

    def test_custom_timeout(self):
        """Test custom timeout value is passed to subprocess."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="success\n", stderr="", returncode=0
            )

            execute_ssh_command("testhost", timeout=30)

            assert mock_run.call_args[1]["timeout"] == 30

    def test_strips_whitespace(self):
        """Test that output whitespace is stripped."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="  success  \n\n", stderr="", returncode=0
            )

            result = execute_ssh_command("testhost")

            assert result == "success"


class TestCheckConnection:
    """Test suite for check_connection function."""

    def test_successful_connection_returns_true(self):
        """Test that successful connection returns True."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="success\n", stderr="", returncode=0
            )

            result = check_connection("testhost")

            assert result is True

    def test_failed_connection_returns_false(self):
        """Test that failed connection returns False."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=255,
                cmd=["ssh", "testhost"],
                stderr="Connection refused",
            )

            result = check_connection("testhost")

            assert result is False

    def test_timeout_returns_false(self):
        """Test that timeout returns False."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["ssh", "testhost"], timeout=10
            )

            result = check_connection("testhost")

            assert result is False

    def test_uses_custom_timeout(self):
        """Test that custom timeout is passed through."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="success\n", stderr="", returncode=0
            )

            check_connection("testhost", timeout=20)

            assert mock_run.call_args[1]["timeout"] == 20
