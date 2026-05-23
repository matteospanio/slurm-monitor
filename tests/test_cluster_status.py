"""Tests for the ClusterStatus widget (queue totals + capacity strip)."""

from slurmhub.queue_stats import ClusterQueueStats
from slurmhub.sinfo_parser import ClusterCapacity
from slurmhub.widgets.cluster_status import ClusterStatus, _format_mem_mb


class TestFormatMemMb:
    def test_terabyte_range(self):
        # 2 TB worth of MB
        assert _format_mem_mb(2 * 1024 * 1024) == "2T"

    def test_zero(self):
        assert _format_mem_mb(0) == "0"

    def test_negative_or_unknown(self):
        assert _format_mem_mb(-1) == "0"


class TestClusterStatusRender:
    def test_waiting_for_data_when_no_stats(self):
        widget = ClusterStatus()
        rendered = str(widget.render())
        assert "waiting for data" in rendered

    def test_renders_queue_only(self):
        widget = ClusterStatus()
        widget.update_stats(
            ClusterQueueStats(total_running=5, total_pending=2, total_other=0)
        )
        rendered = str(widget.render())
        assert "5" in rendered and "running" in rendered
        assert "2" in rendered and "pending" in rendered
        assert "CPU" not in rendered  # no capacity yet

    def test_capacity_strip_when_set(self):
        widget = ClusterStatus()
        widget.update_stats(
            ClusterQueueStats(total_running=5, total_pending=2, total_other=0)
        )
        widget.update_capacity(
            ClusterCapacity(
                nodes_up=18,
                nodes_down=1,
                nodes_drain=0,
                cpus_used=240,
                cpus_total=512,
                gpus_used=12,
                gpus_total=16,
                mem_used_mb=512 * 1024,
                mem_total_mb=2 * 1024 * 1024,
            )
        )
        rendered = str(widget.render())
        assert "240/512 CPU" in rendered
        assert "12/16 GPU" in rendered
        # 512G used / 2T total
        assert "mem" in rendered
        assert "18 up" in rendered
        assert "1 down" in rendered

    def test_no_gpus_omits_gpu_strip(self):
        widget = ClusterStatus()
        widget.update_capacity(
            ClusterCapacity(cpus_used=10, cpus_total=20, gpus_total=0)
        )
        rendered = str(widget.render())
        assert "CPU" in rendered
        assert "GPU" not in rendered
