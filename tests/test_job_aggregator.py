"""Tests for job aggregator functionality."""

from unittest.mock import MagicMock, patch

import pytest

from slurm_monitor.config import SSHConfig
from slurm_monitor.job_aggregator import (
    JobAggregator,
    time_to_seconds,
    filter_jobs_by_state,
    get_job_by_id,
    merge_jobs,
    sort_jobs_by_time,
)
from slurm_monitor.squeue_parser import SlurmJob
from slurm_monitor.ssh_wrapper import SSHClient


@pytest.fixture
def mock_ssh_client():
    client = MagicMock(spec=SSHClient)
    client.host = "testhost"
    return client


class TestMergeJobs:
    """Test suite for merge_jobs function."""

    def test_merge_empty_lists(self):
        assert merge_jobs([], []) == []

    def test_merge_only_active_jobs(self):
        active = [
            SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user"),
            SlurmJob("12346", "job2", "PENDING", "00:00:00", "/home/user"),
        ]
        result = merge_jobs(active, [])
        assert len(result) == 2
        assert result[0].job_id == "12346"

    def test_merge_only_historical_jobs(self):
        historical = [
            SlurmJob("12343", "job1", "COMPLETED", "01:23:45", "/home/user"),
            SlurmJob("12344", "job2", "FAILED", "00:05:30", "/home/user"),
        ]
        result = merge_jobs([], historical)
        assert len(result) == 2
        assert result[0].job_id == "12344"

    def test_merge_no_duplicates(self):
        active = [SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user")]
        historical = [
            SlurmJob("12343", "job2", "COMPLETED", "02:34:56", "/home/user"),
            SlurmJob("12344", "job3", "FAILED", "00:05:30", "/home/user"),
        ]
        result = merge_jobs(active, historical)
        assert len(result) == 3
        assert result[0].job_id == "12345"

    def test_merge_with_duplicates_active_wins(self):
        active = [SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user")]
        historical = [
            SlurmJob("12345", "job1", "PENDING", "00:00:00", "/home/user"),
            SlurmJob("12344", "job2", "COMPLETED", "02:34:56", "/home/user"),
        ]
        result = merge_jobs(active, historical)
        assert len(result) == 2
        job = next(j for j in result if j.job_id == "12345")
        assert job.state == "RUNNING"

    def test_merge_multiple_duplicates(self):
        active = [
            SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user"),
            SlurmJob("12346", "job2", "RUNNING", "00:30:00", "/home/user"),
        ]
        historical = [
            SlurmJob("12345", "job1", "PENDING", "00:00:00", "/home/user"),
            SlurmJob("12346", "job2", "PENDING", "00:00:00", "/home/user"),
            SlurmJob("12344", "job3", "COMPLETED", "02:34:56", "/home/user"),
        ]
        result = merge_jobs(active, historical)
        assert len(result) == 3
        assert next(j for j in result if j.job_id == "12345").state == "RUNNING"
        assert next(j for j in result if j.job_id == "12346").state == "RUNNING"

    def test_merge_sorted_descending(self):
        active = [SlurmJob("12340", "job1", "RUNNING", "01:23:45", "/home/user")]
        historical = [
            SlurmJob("12350", "job2", "COMPLETED", "02:34:56", "/home/user"),
            SlurmJob("12345", "job3", "FAILED", "00:05:30", "/home/user"),
        ]
        result = merge_jobs(active, historical)
        assert [j.job_id for j in result] == ["12350", "12345", "12340"]


class TestSortJobsByTime:
    """Test suite for sort_jobs_by_time function."""

    def test_sort_empty_list(self):
        assert sort_jobs_by_time([]) == []

    def test_sort_single_job(self):
        jobs = [SlurmJob("1", "j", "RUNNING", "01:23:45", "/h")]
        assert len(sort_jobs_by_time(jobs)) == 1

    def test_sort_descending_default(self):
        jobs = [
            SlurmJob("1", "j", "RUNNING", "00:30:00", "/h"),
            SlurmJob("2", "j", "RUNNING", "02:00:00", "/h"),
            SlurmJob("3", "j", "RUNNING", "01:00:00", "/h"),
        ]
        result = sort_jobs_by_time(jobs)
        assert [j.time for j in result] == ["02:00:00", "01:00:00", "00:30:00"]

    def test_sort_ascending(self):
        jobs = [
            SlurmJob("1", "j", "RUNNING", "00:30:00", "/h"),
            SlurmJob("2", "j", "RUNNING", "02:00:00", "/h"),
        ]
        result = sort_jobs_by_time(jobs, reverse=False)
        assert result[0].time == "00:30:00"

    def test_sort_mixed_length_times(self):
        jobs = [
            SlurmJob("1", "j", "RUNNING", "02:00:00", "/h"),
            SlurmJob("2", "j", "RUNNING", "10:30:00", "/h"),
            SlurmJob("3", "j", "RUNNING", "01:00:00", "/h"),
        ]
        result = sort_jobs_by_time(jobs)
        assert result[0].time == "10:30:00"

    def test_sort_with_day_prefix(self):
        jobs = [
            SlurmJob("1", "j", "RUNNING", "1-02:00:00", "/h"),
            SlurmJob("2", "j", "RUNNING", "00:30:00", "/h"),
            SlurmJob("3", "j", "RUNNING", "2-10:00:00", "/h"),
        ]
        result = sort_jobs_by_time(jobs)
        assert result[0].time == "2-10:00:00"

    def test_sort_with_mm_ss_format(self):
        jobs = [
            SlurmJob("1", "j", "RUNNING", "05:30", "/h"),
            SlurmJob("2", "j", "RUNNING", "01:00:00", "/h"),
            SlurmJob("3", "j", "RUNNING", "10:00", "/h"),
        ]
        result = sort_jobs_by_time(jobs)
        assert result[0].time == "01:00:00"


class TestTimeToSeconds:
    """Test suite for time_to_seconds helper function."""

    def test_hhmmss(self):
        assert time_to_seconds("01:23:45") == 1 * 3600 + 23 * 60 + 45

    def test_mmss(self):
        assert time_to_seconds("05:30") == 5 * 60 + 30

    def test_day_prefix(self):
        assert time_to_seconds("2-10:00:00") == 2 * 86400 + 10 * 3600

    def test_zero(self):
        assert time_to_seconds("00:00:00") == 0

    def test_invalid_returns_zero(self):
        assert time_to_seconds("invalid") == 0

    def test_empty_returns_zero(self):
        assert time_to_seconds("") == 0


class TestFilterJobsByState:
    """Test suite for filter_jobs_by_state function."""

    def test_filter_empty_list(self):
        assert filter_jobs_by_state([], ["RUNNING"]) == []

    def test_filter_single_state(self):
        jobs = [
            SlurmJob("1", "j1", "RUNNING", "01:00:00", "/h"),
            SlurmJob("2", "j2", "PENDING", "00:00:00", "/h"),
            SlurmJob("3", "j3", "COMPLETED", "02:00:00", "/h"),
        ]
        result = filter_jobs_by_state(jobs, ["RUNNING"])
        assert len(result) == 1
        assert result[0].state == "RUNNING"

    def test_filter_multiple_states(self):
        jobs = [
            SlurmJob("1", "j1", "RUNNING", "01:00:00", "/h"),
            SlurmJob("2", "j2", "PENDING", "00:00:00", "/h"),
            SlurmJob("3", "j3", "COMPLETED", "02:00:00", "/h"),
        ]
        result = filter_jobs_by_state(jobs, ["RUNNING", "PENDING"])
        assert len(result) == 2

    def test_filter_no_matches(self):
        jobs = [SlurmJob("1", "j1", "RUNNING", "01:00:00", "/h")]
        assert filter_jobs_by_state(jobs, ["COMPLETED"]) == []

    def test_filter_preserves_order(self):
        jobs = [
            SlurmJob("1", "j1", "RUNNING", "01:00:00", "/h"),
            SlurmJob("2", "j2", "RUNNING", "00:30:00", "/h"),
        ]
        result = filter_jobs_by_state(jobs, ["RUNNING"])
        assert result[0].job_id == "1"
        assert result[1].job_id == "2"


class TestGetJobById:
    """Test suite for get_job_by_id function."""

    def test_get_from_empty_list(self):
        assert get_job_by_id([], "12345") is None

    def test_get_existing_job(self):
        jobs = [
            SlurmJob("12345", "job1", "RUNNING", "01:00:00", "/h"),
            SlurmJob("12346", "job2", "PENDING", "00:00:00", "/h"),
        ]
        result = get_job_by_id(jobs, "12345")
        assert result is not None
        assert result.name == "job1"

    def test_get_nonexistent_job(self):
        jobs = [SlurmJob("12345", "j", "RUNNING", "01:00:00", "/h")]
        assert get_job_by_id(jobs, "99999") is None

    def test_get_returns_first_match(self):
        jobs = [
            SlurmJob("12345", "first", "RUNNING", "01:00:00", "/h"),
            SlurmJob("12345", "second", "COMPLETED", "02:00:00", "/h"),
        ]
        result = get_job_by_id(jobs, "12345")
        assert result.name == "first"


class TestJobAggregator:
    """Test suite for JobAggregator class."""

    def test_aggregator_initialization(self, mock_ssh_client):
        aggregator = JobAggregator(mock_ssh_client, timeout=30)
        assert aggregator.client is mock_ssh_client
        assert aggregator.timeout == 30

    def test_aggregator_default_timeout(self, mock_ssh_client):
        aggregator = JobAggregator(mock_ssh_client)
        assert aggregator.timeout == 10

    def test_fetch_all_jobs_success(self, mock_ssh_client):
        active = [SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user")]
        historical = [SlurmJob("12344", "job2", "COMPLETED", "02:34:56", "/home/user")]

        with patch(
            "slurm_monitor.job_aggregator.fetch_squeue_jobs"
        ) as mock_sq, patch(
            "slurm_monitor.job_aggregator.fetch_sacct_jobs"
        ) as mock_sa:
            mock_sq.return_value = active
            mock_sa.return_value = historical

            aggregator = JobAggregator(mock_ssh_client)
            result = aggregator.fetch_all_jobs()

            assert len(result) == 2
            assert result[0].job_id == "12345"

    def test_fetch_all_jobs_with_duplicates(self, mock_ssh_client):
        active = [SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user")]
        historical = [
            SlurmJob("12345", "job1", "PENDING", "00:00:00", "/home/user"),
            SlurmJob("12344", "job2", "COMPLETED", "02:34:56", "/home/user"),
        ]

        with patch(
            "slurm_monitor.job_aggregator.fetch_squeue_jobs"
        ) as mock_sq, patch(
            "slurm_monitor.job_aggregator.fetch_sacct_jobs"
        ) as mock_sa:
            mock_sq.return_value = active
            mock_sa.return_value = historical

            aggregator = JobAggregator(mock_ssh_client)
            result = aggregator.fetch_all_jobs()

            assert len(result) == 2
            job = next(j for j in result if j.job_id == "12345")
            assert job.state == "RUNNING"

    def test_fetch_all_jobs_empty(self, mock_ssh_client):
        with patch(
            "slurm_monitor.job_aggregator.fetch_squeue_jobs"
        ) as mock_sq, patch(
            "slurm_monitor.job_aggregator.fetch_sacct_jobs"
        ) as mock_sa:
            mock_sq.return_value = []
            mock_sa.return_value = []

            aggregator = JobAggregator(mock_ssh_client)
            assert aggregator.fetch_all_jobs() == []

    def test_fetch_all_jobs_passes_timeout(self, mock_ssh_client):
        with patch(
            "slurm_monitor.job_aggregator.fetch_squeue_jobs"
        ) as mock_sq, patch(
            "slurm_monitor.job_aggregator.fetch_sacct_jobs"
        ) as mock_sa:
            mock_sq.return_value = []
            mock_sa.return_value = []

            aggregator = JobAggregator(mock_ssh_client, timeout=30)
            aggregator.fetch_all_jobs()

            assert mock_sq.call_args[1]["timeout"] == 30
            assert mock_sa.call_args[1]["timeout"] == 30

    def test_fetch_all_jobs_passes_client(self, mock_ssh_client):
        with patch(
            "slurm_monitor.job_aggregator.fetch_squeue_jobs"
        ) as mock_sq, patch(
            "slurm_monitor.job_aggregator.fetch_sacct_jobs"
        ) as mock_sa:
            mock_sq.return_value = []
            mock_sa.return_value = []

            aggregator = JobAggregator(mock_ssh_client)
            aggregator.fetch_all_jobs()

            assert mock_sq.call_args[0][0] is mock_ssh_client
            assert mock_sa.call_args[0][0] is mock_ssh_client
