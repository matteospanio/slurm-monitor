"""Tests for the ``--demo`` flag and the DemoSSHClient shim."""

from click.testing import CliRunner
import pytest

from slurmhub import demo_data
from slurmhub.app import SlurmhubApp
from slurmhub.cli import main
from slurmhub.config import AppConfig, ProfileConfig, SSHConfig
from slurmhub.ssh_wrapper import DemoSSHClient
from slurmhub.widgets.job_table import JobTable


class TestDemoSSHClient:
    """The fixture-backed client should answer every command the app issues."""

    def test_connect_and_close_are_noops(self):
        client = DemoSSHClient()
        client.connect()
        client.close()
        assert client.check_connection() is True

    def test_squeue_returns_fixture(self):
        out = DemoSSHClient().execute('squeue --me -o "%i|%j|%T|%M|%Z|%b" --noheader')
        assert "train_resnet50" in out
        assert "RUNNING" in out
        assert "PENDING" in out

    def test_sacct_returns_fixture(self):
        out = DemoSSHClient().execute(
            "sacct -X --format=JobID,JobName,State,Elapsed,WorkDir --units=M -n"
        )
        assert "COMPLETED" in out
        assert "FAILED" in out

    def test_sinfo_nodes_vs_partitions(self):
        client = DemoSSHClient()
        nodes = client.execute('sinfo -h -N -o "%N|%R|%T|%C|%e|%m|%G|%E"')
        partitions = client.execute('sinfo -h -o "%R|%D|%C|%G|%m|%a"')
        assert "node-gpu-01" in nodes
        assert "node-cpu-12" in nodes
        # The partition response should NOT contain per-node names.
        assert "node-gpu-01" not in partitions
        assert "gpu|" in partitions

    def test_scontrol_show_job_known_id(self):
        out = DemoSSHClient().execute("scontrol show job 421578")
        assert "JobState=RUNNING" in out
        assert "JobName=train_resnet50" in out

    def test_scontrol_show_job_unknown_id_is_empty(self):
        assert DemoSSHClient().execute("scontrol show job 999999") == ""

    def test_batch_script(self):
        out = DemoSSHClient().execute("scontrol write batch_script 421578 -")
        assert "#SBATCH" in out
        assert "train_resnet50" in out

    def test_scancel_succeeds_silently(self):
        # The app expects an empty string on success.
        assert DemoSSHClient().execute("scancel 421578") == ""

    def test_stream_command_replays_log_fixture(self):
        client = DemoSSHClient()
        received: list[str] = []
        stop = {"now": False}

        def on_line(line: str) -> None:
            received.append(line)
            if len(received) >= 5:
                stop["now"] = True

        client.stream_command(
            "tail -n 50 -f /home/demo-user/projects/vision-models/logs/421578.out",
            on_line=on_line,
            should_stop=lambda: stop["now"],
            poll_interval=0.0,
        )

        assert len(received) >= 5
        assert any("Epoch" in line for line in received)


class TestDemoModeApp:
    """End-to-end: ``--demo`` makes the app render fixture jobs."""

    def _demo_config(self) -> AppConfig:
        profile = ProfileConfig(
            name="demo",
            ssh=SSHConfig(host=demo_data.DEMO_HOST, username=demo_data.DEMO_USERNAME),
        )
        return AppConfig(profiles={"demo": profile})

    def test_app_uses_demo_ssh_client(self):
        app = SlurmhubApp(config=self._demo_config(), demo=True)
        tab = app._profile_tabs["demo"]
        assert isinstance(tab.ssh_client, DemoSSHClient)

    def test_app_uses_regular_ssh_client_without_demo(self):
        from slurmhub.ssh_wrapper import SSHClient

        app = SlurmhubApp(config=self._demo_config(), demo=False)
        tab = app._profile_tabs["demo"]
        # Should be the regular client, not the demo subclass.
        assert isinstance(tab.ssh_client, SSHClient)
        assert not isinstance(tab.ssh_client, DemoSSHClient)

    @pytest.mark.asyncio
    async def test_demo_mode_populates_job_table(self):
        app = SlurmhubApp(config=self._demo_config(), demo=True)
        async with app.run_test() as pilot:
            # Initial refresh runs on mount; let the worker complete.
            await pilot.pause(0.4)
            tab = app._profile_tabs["demo"]
            assert tab.jobs, "demo mode should fetch fixture jobs on mount"

            table = app.query_one("#table-demo", JobTable)
            assert table.row_count == len(tab.jobs)

            # The fixture mixes states; confirm we see at least one
            # RUNNING and one PENDING job.
            states = {j.state for j in tab.jobs}
            assert "RUNNING" in states
            assert "PENDING" in states


class TestDemoCliFlag:
    """``slurmhub --demo`` should run without touching SSH."""

    def test_demo_flag_present_in_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "--demo" in result.output

    def test_demo_invocation_constructs_app_with_demo_flag(self, monkeypatch):
        captured = {}

        class FakeApp:
            def __init__(self, config, demo=False):
                captured["config"] = config
                captured["demo"] = demo

            def run(self):
                captured["ran"] = True

        monkeypatch.setattr("slurmhub.app.SlurmhubApp", FakeApp)

        runner = CliRunner()
        result = runner.invoke(main, ["--demo"])

        assert result.exit_code == 0
        assert captured.get("ran") is True
        assert captured.get("demo") is True
        # The synthetic config should have a single 'demo' profile.
        assert list(captured["config"].profiles.keys()) == ["demo"]
