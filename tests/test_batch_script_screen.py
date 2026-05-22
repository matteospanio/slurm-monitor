"""Tests for the BatchScriptScreen viewer."""

from unittest.mock import MagicMock, patch

import pytest

from slurm_monitor.config import SSHConfig
from slurm_monitor.squeue_parser import SlurmJob
from slurm_monitor.ssh_wrapper import SSHClient
from slurm_monitor.widgets.batch_script_screen import BatchScriptScreen


@pytest.fixture
def job():
    return SlurmJob(
        job_id="42", name="train", state="RUNNING", time="00:01:00"
    )


@pytest.fixture
def ssh_client():
    return SSHClient(SSHConfig(host="host"))


class TestBatchScriptScreen:
    def test_construction(self, job, ssh_client):
        screen = BatchScriptScreen(job, ssh_client, ssh_timeout=5)
        assert screen.job is job
        assert screen.ssh_timeout == 5
        assert screen._script_text is None

    def test_fetch_script_uses_scontrol_write(self, job, ssh_client):
        screen = BatchScriptScreen(job, ssh_client)
        with patch.object(
            ssh_client, "execute", return_value="#!/bin/bash\necho hi"
        ) as mock_exec:
            result = screen._fetch_script()
        mock_exec.assert_called_once()
        cmd = mock_exec.call_args.args[0]
        assert "scontrol write batch_script" in cmd
        assert "42" in cmd
        assert result == "#!/bin/bash\necho hi"

    def test_save_to_disk_writes_script(self, job, ssh_client, tmp_path):
        screen = BatchScriptScreen(job, ssh_client)
        screen._script_text = "#!/bin/bash\necho ok\n"
        target = tmp_path / "out.sh"
        with patch.object(
            BatchScriptScreen, "_default_save_path", return_value=target
        ), patch.object(
            type(screen), "app", new_callable=lambda: property(lambda self: MagicMock())
        ), patch.object(BatchScriptScreen, "notify"):
            screen.action_save_to_disk()
        assert target.read_text() == "#!/bin/bash\necho ok\n"

    def test_save_to_disk_requires_loaded_script(self, job, ssh_client):
        screen = BatchScriptScreen(job, ssh_client)
        screen._script_text = None
        with patch.object(
            type(screen), "app", new_callable=lambda: property(lambda self: MagicMock())
        ), patch.object(BatchScriptScreen, "notify") as mock_notify:
            screen.action_save_to_disk()
        # Should warn rather than crash
        assert mock_notify.called
