"""Tests for cluster-wide queue statistics and pending job details."""

from unittest.mock import MagicMock

from slurm_monitor.queue_stats import (
    ClusterQueueStats,
    PendingInfo,
    compute_queue_ranks,
    fetch_cluster_queue_stats,
    fetch_pending_details,
    parse_cluster_queue_stats,
    parse_pending_details,
    parse_queue_ranks,
)


class TestParseClusterQueueStats:
    def test_mixed_states(self):
        output = "RUNNING\nRUNNING\nPENDING\nRUNNING\nPENDING\nCOMPLETING\n"
        stats = parse_cluster_queue_stats(output)
        assert stats.total_running == 3
        assert stats.total_pending == 2
        assert stats.total_other == 1

    def test_empty_output(self):
        stats = parse_cluster_queue_stats("")
        assert stats.total_running == 0
        assert stats.total_pending == 0
        assert stats.total_other == 0

    def test_only_running(self):
        output = "RUNNING\nRUNNING\n"
        stats = parse_cluster_queue_stats(output)
        assert stats.total_running == 2
        assert stats.total_pending == 0

    def test_blank_lines_ignored(self):
        output = "RUNNING\n\n\nPENDING\n"
        stats = parse_cluster_queue_stats(output)
        assert stats.total_running == 1
        assert stats.total_pending == 1


class TestParsePendingDetails:
    def test_typical_output(self):
        output = (
            "12345|Resources|5000|2026-04-13T10:00:00|normal\n"
            "12346|Priority|3000|2026-04-13T09:30:00|high\n"
        )
        result = parse_pending_details(output)
        assert len(result) == 2
        assert result["12345"] == PendingInfo(
            reason="Resources", priority=5000,
            submit_time="2026-04-13T10:00:00", qos="normal",
        )
        assert result["12346"].priority == 3000
        assert result["12346"].qos == "high"

    def test_empty_output(self):
        assert parse_pending_details("") == {}

    def test_malformed_line_skipped(self):
        output = "12345|Resources\n12346|Priority|3000|2026-04-13T09:30:00|high\n"
        result = parse_pending_details(output)
        assert len(result) == 1
        assert "12346" in result

    def test_invalid_priority_skipped(self):
        output = "12345|Resources|notanumber|2026-04-13T10:00:00|normal\n"
        result = parse_pending_details(output)
        assert len(result) == 0


class TestParseQueueRanks:
    def test_priority_sorted_list(self):
        output = "9000|100\n8000|200\n7000|300\n6000|400\n"
        job_ids = parse_queue_ranks(output)
        assert job_ids == ["100", "200", "300", "400"]

    def test_empty_output(self):
        assert parse_queue_ranks("") == []

    def test_blank_lines_ignored(self):
        output = "9000|100\n\n8000|200\n"
        job_ids = parse_queue_ranks(output)
        assert job_ids == ["100", "200"]


class TestComputeQueueRanks:
    def test_ranks_computed_correctly(self):
        client = MagicMock()
        client.execute.return_value = "9000|100\n8000|200\n7000|300\n6000|400\n"

        ranks = compute_queue_ranks(client, ["200", "400"])
        assert ranks == {"200": 2, "400": 4}

    def test_empty_user_jobs(self):
        client = MagicMock()
        ranks = compute_queue_ranks(client, [])
        assert ranks == {}
        client.execute.assert_not_called()

    def test_user_job_not_in_queue(self):
        client = MagicMock()
        client.execute.return_value = "9000|100\n8000|200\n"

        ranks = compute_queue_ranks(client, ["999"])
        assert ranks == {}


class TestFetchClusterQueueStats:
    def test_fetches_and_parses(self):
        client = MagicMock()
        client.execute.return_value = "RUNNING\nPENDING\nRUNNING\n"

        stats = fetch_cluster_queue_stats(client)
        assert stats.total_running == 2
        assert stats.total_pending == 1
        assert stats.fetched_at is not None
        client.execute.assert_called_once()


class TestFetchPendingDetails:
    def test_fetches_and_parses(self):
        client = MagicMock()
        client.execute.return_value = (
            "12345|Resources|5000|2026-04-13T10:00:00|normal\n"
        )

        result = fetch_pending_details(client)
        assert "12345" in result
        assert result["12345"].reason == "Resources"
        client.execute.assert_called_once()
