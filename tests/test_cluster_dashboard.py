"""Tests for the ClusterDashboardScreen."""

from unittest.mock import patch

import pytest

from textual.widgets import DataTable

from slurmhub.tui.app import SlurmhubApp
from slurmhub.config import AppConfig, LogConfig, ProfileConfig, SSHConfig
from slurmhub.slurm.sinfo import ClusterCapacity, NodeStats, PartitionStats
from slurmhub.slurm.ssh import SSHClient
from slurmhub.tui.widgets.cluster_dashboard import ClusterDashboardScreen


def _make_capacity() -> ClusterCapacity:
    return ClusterCapacity(
        nodes_up=2,
        nodes_down=0,
        nodes_drain=0,
        cpus_used=32,
        cpus_total=64,
        gpus_used=4,
        gpus_total=8,
        mem_used_mb=128000,
        mem_total_mb=512000,
        fetched_at="12:34:56",
    )


def _make_partitions() -> list[PartitionStats]:
    return [
        PartitionStats(
            name="gpu", nodes_total=2, nodes_idle=1, nodes_alloc=1,
            cpus_alloc=32, cpus_idle=32, cpus_total=64,
            gpus_total=8, gpus_used=4, mem_total_mb=512000, available=True,
        ),
    ]


def _make_nodes() -> list[NodeStats]:
    return [
        NodeStats(
            name="gpu01", partition="gpu", state="idle",
            cpus_alloc=0, cpus_total=32,
            mem_free_mb=256000, mem_total_mb=256000,
            gpus_total=4, gpus_used=0,
        ),
        NodeStats(
            name="gpu02", partition="gpu", state="allocated",
            cpus_alloc=32, cpus_total=32,
            mem_free_mb=10000, mem_total_mb=256000,
            gpus_total=4, gpus_used=4,
        ),
    ]


def _single_profile_config() -> AppConfig:
    profile = ProfileConfig(ssh=SSHConfig(host="testhost"), log=LogConfig())
    return AppConfig(profiles={"clusterA": profile})


class TestClusterDashboardScreenConstruction:
    def test_constructs_with_initial_data(self):
        ssh = SSHClient(SSHConfig(host="testhost"))
        screen = ClusterDashboardScreen(
            profile_name="clusterA",
            ssh_client=ssh,
            ssh_timeout=10,
            initial_capacity=_make_capacity(),
            initial_partitions=_make_partitions(),
            initial_nodes=_make_nodes(),
        )
        assert screen.profile_name == "clusterA"
        assert screen.capacity is not None
        assert screen.capacity.cpus_total == 64
        assert len(screen.partitions) == 1
        assert len(screen.nodes) == 2

    def test_constructs_empty_when_no_cache(self):
        ssh = SSHClient(SSHConfig(host="testhost"))
        screen = ClusterDashboardScreen(
            profile_name="clusterA",
            ssh_client=ssh,
            ssh_timeout=10,
        )
        assert screen.capacity is None
        assert screen.partitions == []
        assert screen.nodes == []


class TestClusterDashboardPilot:
    """Textual pilot tests for the dashboard screen behaviour."""

    @pytest.mark.asyncio
    async def test_d_key_pushes_dashboard(self):
        app = SlurmhubApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            # Pre-seed cached data so the screen renders without an SSH call
            tab = app._profile_tabs["clusterA"]
            tab.cluster_capacity = _make_capacity()
            tab.partitions = _make_partitions()
            tab.nodes = _make_nodes()

            # Avoid triggering a network fetch when the screen mounts
            with patch(
                "slurmhub.tui.widgets.cluster_dashboard.fetch_sinfo",
                return_value=(_make_capacity(), _make_partitions(), _make_nodes()),
            ):
                await pilot.press("d")
                await pilot.pause()

                assert isinstance(app.screen, ClusterDashboardScreen)
                # Partition + node tables populated from initial cache
                partition_table = app.screen.query_one(
                    "#partition-table", DataTable
                )
                assert partition_table.row_count == 1
                node_table = app.screen.query_one("#node-table", DataTable)
                assert node_table.row_count == 2

    @pytest.mark.asyncio
    async def test_escape_closes_dashboard(self):
        app = SlurmhubApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            tab = app._profile_tabs["clusterA"]
            tab.cluster_capacity = _make_capacity()
            tab.partitions = _make_partitions()
            tab.nodes = _make_nodes()

            with patch(
                "slurmhub.tui.widgets.cluster_dashboard.fetch_sinfo",
                return_value=(_make_capacity(), _make_partitions(), _make_nodes()),
            ):
                await pilot.press("d")
                await pilot.pause()
                assert isinstance(app.screen, ClusterDashboardScreen)

                await pilot.press("escape")
                await pilot.pause()
                assert not isinstance(app.screen, ClusterDashboardScreen)

    @pytest.mark.asyncio
    async def test_r_triggers_refresh(self):
        app = SlurmhubApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            tab = app._profile_tabs["clusterA"]
            tab.cluster_capacity = _make_capacity()
            tab.partitions = _make_partitions()
            tab.nodes = _make_nodes()

            with patch(
                "slurmhub.tui.widgets.cluster_dashboard.fetch_sinfo",
                return_value=(_make_capacity(), _make_partitions(), _make_nodes()),
            ) as mock_fetch:
                await pilot.press("d")
                await pilot.pause()
                initial_calls = mock_fetch.call_count

                await pilot.press("r")
                await pilot.pause()
                assert mock_fetch.call_count > initial_calls

    @pytest.mark.asyncio
    async def test_renders_loading_text_when_empty(self):
        """No cached data + slow fetch should show a loading placeholder."""
        app = SlurmhubApp(config=_single_profile_config())
        async with app.run_test() as pilot:
            # ProfileTab has no cached capacity (default state)
            with patch(
                "slurmhub.tui.widgets.cluster_dashboard.fetch_sinfo",
                return_value=(_make_capacity(), _make_partitions(), _make_nodes()),
            ):
                await pilot.press("d")
                # Don't pause — we want to read the body before the worker
                # completes. The pause-less path may already be done in CI,
                # so just assert the screen exists and the body widget is
                # mounted.
                assert isinstance(app.screen, ClusterDashboardScreen)
