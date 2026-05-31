"""Tests for the LogScreen widget."""

from unittest.mock import MagicMock, patch

import pytest

from slurmhub.config import SSHConfig
from slurmhub.slurm.squeue import SlurmJob
from slurmhub.slurm.ssh import SSHClient
from slurmhub.tui.widgets.log_viewer import LogScreen, find_match_indices


@pytest.fixture
def mock_job():
    return SlurmJob(
        job_id="12345",
        name="test-job",
        state="RUNNING",
        time="1:00:00",
        work_dir="/home/user/project",
    )


@pytest.fixture
def mock_ssh_client():
    config = SSHConfig(host="testhost")
    return SSHClient(config)


class TestLogScreen:
    def test_creates_with_job_info(self, mock_job, mock_ssh_client):
        screen = LogScreen(mock_job, "/path/to/log.out", mock_ssh_client)
        assert screen.job == mock_job
        assert screen.log_path == "/path/to/log.out"
        assert screen.tail_lines == 50

    def test_custom_tail_lines(self, mock_job, mock_ssh_client):
        screen = LogScreen(
            mock_job, "/path/to/log.out", mock_ssh_client, tail_lines=100
        )
        assert screen.tail_lines == 100

    def test_close_signals_stream_to_stop(self, mock_job, mock_ssh_client):
        screen = LogScreen(mock_job, "/path/to/log.out", mock_ssh_client)
        assert screen._stop_stream is False

        with patch.object(
            type(screen), "app", new_callable=lambda: property(lambda self: MagicMock())
        ):
            screen.action_close()

        assert screen._stop_stream is True

    def test_close_is_idempotent(self, mock_job, mock_ssh_client):
        screen = LogScreen(mock_job, "/path/to/log.out", mock_ssh_client)

        with patch.object(
            type(screen), "app", new_callable=lambda: property(lambda self: MagicMock())
        ):
            screen.action_close()
            screen.action_close()

        assert screen._stop_stream is True

    def test_build_stream_command_uses_configured_template(
        self, mock_job, mock_ssh_client
    ):
        screen = LogScreen(
            mock_job,
            "/tmp/my logs/log.out",
            mock_ssh_client,
            tail_lines=50,
            view_command_template="less +F {log_path}",
        )
        assert screen._build_stream_command() == "less +F '/tmp/my logs/log.out'"


class TestFindMatchIndices:
    """Search predicate used by the in-log search bar."""

    def test_empty_query_returns_no_matches(self):
        assert find_match_indices(["hello", "world"], "") == []

    def test_case_insensitive(self):
        lines = ["Hello World", "no match", "hELLo again"]
        assert find_match_indices(lines, "hello") == [0, 2]

    def test_substring_match(self):
        lines = ["abc def ghi", "ghi jkl"]
        assert find_match_indices(lines, "def") == [0]

    def test_no_matches(self):
        assert find_match_indices(["a", "b"], "xyz") == []


class TestLogScreenSaveAndYank:
    """save-to-disk and yank-line use only the in-memory mirror buffer."""

    def test_save_to_disk_writes_lines(self, tmp_path, mock_job, mock_ssh_client):
        screen = LogScreen(mock_job, "/path/log.out", mock_ssh_client)
        screen._lines = ["alpha\n", "beta", "gamma\n"]

        target = tmp_path / "out.log"
        with (
            patch.object(LogScreen, "_default_save_path", return_value=target),
            patch.object(
                type(screen),
                "app",
                new_callable=lambda: property(lambda self: MagicMock()),
            ),
            patch.object(LogScreen, "notify"),
        ):
            screen.action_save_to_disk()

        content = target.read_text(encoding="utf-8")
        # Trailing newlines are added when missing.
        assert "alpha" in content
        assert "beta" in content
        assert "gamma" in content
        assert content.endswith("\n")

    def test_yank_falls_back_to_last_line_without_search(
        self, mock_job, mock_ssh_client
    ):
        screen = LogScreen(mock_job, "/path/log.out", mock_ssh_client)
        screen._lines = ["first", "last line"]

        with (
            patch(
                "slurmhub.tui.widgets._clipboard.copy_osc52", return_value=True
            ) as mock_copy,
            patch.object(
                type(screen),
                "app",
                new_callable=lambda: property(lambda self: MagicMock()),
            ),
            patch.object(LogScreen, "notify"),
        ):
            screen.action_yank_line()

        mock_copy.assert_called_once_with("last line")
