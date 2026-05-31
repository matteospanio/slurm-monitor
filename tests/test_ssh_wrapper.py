"""Tests for SSH wrapper functionality."""

import os
import socket
from unittest.mock import MagicMock, mock_open, patch, PropertyMock

import paramiko
import pytest

from slurmhub.config import SSHConfig
from slurmhub.slurm.ssh import (
    SSHAuthenticationError,
    SSHClient,
    SSHConnectionError,
    SSHTimeoutError,
)


@pytest.fixture
def ssh_config():
    return SSHConfig(host="testhost")


@pytest.fixture
def ssh_config_full():
    return SSHConfig(
        host="testhost",
        port=2222,
        username="testuser",
        key_filename="~/.ssh/id_test",
    )


@pytest.fixture
def ssh_config_jump():
    return SSHConfig(
        host="targethost",
        username="testuser",
        jump_host="bastion.edu",
    )


class TestSSHClientConnect:
    """Test suite for SSHClient.connect."""

    def test_connect_basic(self, ssh_config):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            client = SSHClient(ssh_config)
            client.connect()

            mock_instance.set_missing_host_key_policy.assert_called_once()
            mock_instance.connect.assert_called_once()
            kwargs = mock_instance.connect.call_args[1]
            assert kwargs["hostname"] == "testhost"
            assert kwargs["port"] == 22
            assert kwargs["timeout"] == 10

    def test_connect_with_full_config(self, ssh_config_full):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            client = SSHClient(ssh_config_full)
            client.connect()

            kwargs = mock_instance.connect.call_args[1]
            assert kwargs["hostname"] == "testhost"
            assert kwargs["port"] == 2222
            assert kwargs["username"] == "testuser"
            assert kwargs["key_filename"] == "~/.ssh/id_test"

    def test_connect_reuses_existing(self, ssh_config):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_transport = MagicMock()
            mock_instance.get_transport.return_value = mock_transport
            mock_cls.return_value = mock_instance

            client = SSHClient(ssh_config)
            client.connect()
            client.connect()  # second call should reuse

            # connect() called only once since transport is alive
            assert mock_instance.connect.call_count == 1

    def test_connect_timeout_raises(self, ssh_config):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.connect.side_effect = socket.timeout("timed out")
            mock_cls.return_value = mock_instance

            client = SSHClient(ssh_config)
            with pytest.raises(SSHTimeoutError, match="timed out"):
                client.connect()

    def test_connect_auth_failure_raises(self, ssh_config):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.connect.side_effect = paramiko.AuthenticationException(
                "auth failed"
            )
            mock_cls.return_value = mock_instance

            client = SSHClient(ssh_config)
            with pytest.raises(SSHConnectionError, match="authentication.*failed"):
                client.connect()

    def test_connect_ssh_error_raises(self, ssh_config):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.connect.side_effect = paramiko.SSHException(
                "connection refused"
            )
            mock_cls.return_value = mock_instance

            client = SSHClient(ssh_config)
            with pytest.raises(SSHConnectionError, match="connection refused"):
                client.connect()

    def test_connect_via_jump_host(self, ssh_config_jump):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_jump = MagicMock()
            mock_target = MagicMock()
            mock_transport = MagicMock()
            mock_channel = MagicMock()
            mock_jump.get_transport.return_value = mock_transport
            mock_transport.open_channel.return_value = mock_channel

            mock_cls.side_effect = [mock_target, mock_jump]

            client = SSHClient(ssh_config_jump)
            client.connect()

            # Jump client connected to bastion
            mock_jump.connect.assert_called_once()
            jump_kwargs = mock_jump.connect.call_args[1]
            assert jump_kwargs["hostname"] == "bastion.edu"

            # Target connected through channel
            mock_target.connect.assert_called_once()
            target_kwargs = mock_target.connect.call_args[1]
            assert target_kwargs["hostname"] == "targethost"
            assert target_kwargs["sock"] == mock_channel


class TestSSHClientExecute:
    """Test suite for SSHClient.execute."""

    def test_execute_success(self, ssh_config):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            mock_stdout = MagicMock()
            mock_stdout.read.return_value = b"output\n"
            mock_stdout.channel.recv_exit_status.return_value = 0
            mock_stderr = MagicMock()
            mock_stderr.read.return_value = b""
            mock_instance.exec_command.return_value = (
                MagicMock(),
                mock_stdout,
                mock_stderr,
            )

            client = SSHClient(ssh_config)
            result = client.execute("echo hello")

            assert result == "output"
            mock_instance.exec_command.assert_called_once_with(
                "echo hello", timeout=10
            )

    def test_execute_strips_whitespace(self, ssh_config):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            mock_stdout = MagicMock()
            mock_stdout.read.return_value = b"  output  \n\n"
            mock_stdout.channel.recv_exit_status.return_value = 0
            mock_stderr = MagicMock()
            mock_instance.exec_command.return_value = (
                MagicMock(),
                mock_stdout,
                mock_stderr,
            )

            client = SSHClient(ssh_config)
            result = client.execute("test")

            assert result == "output"

    def test_execute_nonzero_exit_raises(self, ssh_config):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            mock_stdout = MagicMock()
            mock_stdout.read.return_value = b""
            mock_stdout.channel.recv_exit_status.return_value = 1
            mock_stderr = MagicMock()
            mock_stderr.read.return_value = b"command not found"
            mock_instance.exec_command.return_value = (
                MagicMock(),
                mock_stdout,
                mock_stderr,
            )

            client = SSHClient(ssh_config)
            with pytest.raises(SSHConnectionError, match="command not found"):
                client.execute("bad_command")

    def test_execute_timeout_raises(self, ssh_config):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.exec_command.side_effect = socket.timeout("timed out")

            client = SSHClient(ssh_config)
            with pytest.raises(SSHTimeoutError, match="timed out"):
                client.execute("slow_command", timeout=5)

    def test_execute_custom_timeout(self, ssh_config):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            mock_stdout = MagicMock()
            mock_stdout.read.return_value = b"ok"
            mock_stdout.channel.recv_exit_status.return_value = 0
            mock_stderr = MagicMock()
            mock_instance.exec_command.return_value = (
                MagicMock(),
                mock_stdout,
                mock_stderr,
            )

            client = SSHClient(ssh_config)
            client.execute("test", timeout=30)

            mock_instance.exec_command.assert_called_once_with(
                "test", timeout=30
            )


class TestSSHClientCheckConnection:
    """Test suite for SSHClient.check_connection."""

    def test_check_connection_success(self, ssh_config):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            mock_stdout = MagicMock()
            mock_stdout.read.return_value = b"success"
            mock_stdout.channel.recv_exit_status.return_value = 0
            mock_stderr = MagicMock()
            mock_instance.exec_command.return_value = (
                MagicMock(),
                mock_stdout,
                mock_stderr,
            )

            client = SSHClient(ssh_config)
            assert client.check_connection() is True

    def test_check_connection_failure(self, ssh_config):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.connect.side_effect = paramiko.SSHException("fail")
            mock_cls.return_value = mock_instance

            client = SSHClient(ssh_config)
            assert client.check_connection() is False


class TestSSHClientClose:
    """Test suite for SSHClient.close and context manager."""

    def test_close(self, ssh_config):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            client = SSHClient(ssh_config)
            client.connect()
            client.close()

            mock_instance.close.assert_called_once()

    def test_context_manager(self, ssh_config):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            with SSHClient(ssh_config) as client:
                pass

            # close is called on exit (but no paramiko client was created
            # since we didn't call connect)

    def test_host_property(self, ssh_config):
        client = SSHClient(ssh_config)
        assert client.host == "testhost"


class TestSSHConfigParsing:
    """Test that ~/.ssh/config host aliases are resolved by paramiko."""

    SSH_CONFIG_CONTENT = """\
Host myalias
    HostName real.server.com
    User remoteuser
    Port 2222
    IdentityFile ~/.ssh/id_custom

Host proxy-host
    HostName behind.firewall.com
    User proxyuser
    ProxyCommand ssh -W %h:%p bastion
"""

    def _make_client_with_ssh_config(self, config: SSHConfig):
        """Create an SSHClient and build kwargs with a fake ~/.ssh/config."""
        client = SSHClient(config)
        with patch("os.path.exists", return_value=True), patch(
            "builtins.open", mock_open(read_data=self.SSH_CONFIG_CONTENT)
        ):
            return client._build_connect_kwargs(timeout=10)

    def test_resolves_hostname_from_alias(self):
        config = SSHConfig(host="myalias")
        kwargs = self._make_client_with_ssh_config(config)
        assert kwargs["hostname"] == "real.server.com"

    def test_resolves_user_from_ssh_config(self):
        config = SSHConfig(host="myalias")
        kwargs = self._make_client_with_ssh_config(config)
        assert kwargs["username"] == "remoteuser"

    def test_resolves_port_from_ssh_config(self):
        config = SSHConfig(host="myalias")
        kwargs = self._make_client_with_ssh_config(config)
        assert kwargs["port"] == 2222

    def test_resolves_identity_file_from_ssh_config(self):
        config = SSHConfig(host="myalias")
        kwargs = self._make_client_with_ssh_config(config)
        assert kwargs["key_filename"] == [os.path.expanduser("~/.ssh/id_custom")]

    def test_explicit_config_overrides_ssh_config(self):
        config = SSHConfig(
            host="myalias", username="override", port=3333, key_filename="/my/key"
        )
        kwargs = self._make_client_with_ssh_config(config)
        # hostname still resolved from ssh config
        assert kwargs["hostname"] == "real.server.com"
        # but user, port, key overridden by explicit config
        assert kwargs["username"] == "override"
        assert kwargs["port"] == 3333
        assert kwargs["key_filename"] == "/my/key"

    def test_unknown_host_passes_through(self):
        config = SSHConfig(host="unknown-host")
        kwargs = self._make_client_with_ssh_config(config)
        assert kwargs["hostname"] == "unknown-host"

    def test_proxy_command_from_ssh_config(self):
        config = SSHConfig(host="proxy-host")
        kwargs = self._make_client_with_ssh_config(config)
        assert kwargs["hostname"] == "behind.firewall.com"
        assert isinstance(kwargs["sock"], paramiko.ProxyCommand)

    def test_no_ssh_config_file(self):
        config = SSHConfig(host="somehost")
        client = SSHClient(config)
        with patch("os.path.exists", return_value=False):
            kwargs = client._build_connect_kwargs(timeout=10)
        assert kwargs["hostname"] == "somehost"


class TestSSHAuthenticationError:
    """Test suite for SSHAuthenticationError and runtime credentials."""

    def test_auth_error_is_subclass_of_connection_error(self):
        assert issubclass(SSHAuthenticationError, SSHConnectionError)

    def test_auth_failure_raises_authentication_error(self, ssh_config):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.connect.side_effect = paramiko.AuthenticationException(
                "auth failed"
            )
            mock_cls.return_value = mock_instance

            client = SSHClient(ssh_config)
            with pytest.raises(SSHAuthenticationError, match="authentication.*failed"):
                client.connect()

    def test_set_credentials_stores_password(self, ssh_config):
        client = SSHClient(ssh_config)
        client.set_credentials(password="secret")
        assert client._runtime_password == "secret"
        assert client._runtime_passphrase is None

    def test_set_credentials_stores_passphrase(self, ssh_config):
        client = SSHClient(ssh_config)
        client.set_credentials(passphrase="keypass")
        assert client._runtime_passphrase == "keypass"
        assert client._runtime_password is None

    def test_set_credentials_closes_existing_connection(self, ssh_config):
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            client = SSHClient(ssh_config)
            client.connect()
            client.set_credentials(password="secret")

            mock_instance.close.assert_called_once()
            assert client._client is None

    def test_runtime_password_in_connect_kwargs(self, ssh_config):
        client = SSHClient(ssh_config)
        client.set_credentials(password="secret")
        with patch("os.path.exists", return_value=False):
            kwargs = client._build_connect_kwargs(timeout=10)
        assert kwargs["password"] == "secret"

    def test_runtime_passphrase_in_connect_kwargs(self, ssh_config):
        client = SSHClient(ssh_config)
        client.set_credentials(passphrase="keypass")
        with patch("os.path.exists", return_value=False):
            kwargs = client._build_connect_kwargs(timeout=10)
        assert kwargs["passphrase"] == "keypass"

    def test_runtime_passphrase_overrides_config(self):
        config = SSHConfig(host="testhost", passphrase="config-pass")
        client = SSHClient(config)
        client.set_credentials(passphrase="runtime-pass")
        with patch("os.path.exists", return_value=False):
            kwargs = client._build_connect_kwargs(timeout=10)
        assert kwargs["passphrase"] == "runtime-pass"

    def test_config_passphrase_used_without_runtime(self):
        config = SSHConfig(host="testhost", passphrase="config-pass")
        client = SSHClient(config)
        with patch("os.path.exists", return_value=False):
            kwargs = client._build_connect_kwargs(timeout=10)
        assert kwargs["passphrase"] == "config-pass"

    def test_runtime_credentials_disable_agent(self, ssh_config):
        """When credentials are set, agent and key discovery are disabled."""
        client = SSHClient(ssh_config)
        client.set_credentials(password="secret")
        with patch("os.path.exists", return_value=False):
            kwargs = client._build_connect_kwargs(timeout=10)
        assert kwargs["allow_agent"] is False
        assert kwargs["look_for_keys"] is False

    def test_no_credentials_enables_agent(self, ssh_config):
        """Without runtime credentials, agent and key discovery are enabled."""
        client = SSHClient(ssh_config)
        with patch("os.path.exists", return_value=False):
            kwargs = client._build_connect_kwargs(timeout=10)
        assert kwargs["allow_agent"] is True
        assert kwargs["look_for_keys"] is True

    def test_transport_crash_raises_authentication_error(self, ssh_config):
        """AttributeError from dead transport during auth is treated as auth error."""
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.connect.side_effect = AttributeError(
                "'NoneType' object has no attribute '_log'"
            )
            mock_cls.return_value = mock_instance

            client = SSHClient(ssh_config)
            with pytest.raises(SSHAuthenticationError, match="too many agent keys"):
                client.connect()

    def test_no_existing_session_raises_authentication_error(self, ssh_config):
        """SSHException 'No existing session' (agent unavailable) is auth error."""
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.connect.side_effect = paramiko.SSHException(
                "No existing session"
            )
            mock_cls.return_value = mock_instance

            client = SSHClient(ssh_config)
            with pytest.raises(SSHAuthenticationError, match="No existing session"):
                client.connect()

    def test_generic_ssh_exception_raises_connection_error(self, ssh_config):
        """Non-auth SSHException should still raise SSHConnectionError."""
        with patch("paramiko.SSHClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.connect.side_effect = paramiko.SSHException(
                "Incompatible ssh peer"
            )
            mock_cls.return_value = mock_instance

            client = SSHClient(ssh_config)
            with pytest.raises(SSHConnectionError):
                client.connect()
            # Ensure it's NOT SSHAuthenticationError
            with pytest.raises(SSHConnectionError) as exc_info:
                client2 = SSHClient(ssh_config)
                client2.connect()
            assert not isinstance(exc_info.value, SSHAuthenticationError)

    def test_runtime_credentials_in_jump_host(self):
        config = SSHConfig(
            host="targethost", username="testuser", jump_host="bastion.edu"
        )
        with patch("paramiko.SSHClient") as mock_cls:
            mock_jump = MagicMock()
            mock_target = MagicMock()
            mock_transport = MagicMock()
            mock_channel = MagicMock()
            mock_jump.get_transport.return_value = mock_transport
            mock_transport.open_channel.return_value = mock_channel

            mock_cls.side_effect = [mock_target, mock_jump]

            client = SSHClient(config)
            client.set_credentials(password="secret", passphrase="keypass")
            client.connect()

            jump_kwargs = mock_jump.connect.call_args[1]
            assert jump_kwargs["password"] == "secret"
            assert jump_kwargs["passphrase"] == "keypass"
