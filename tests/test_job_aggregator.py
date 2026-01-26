"""Tests for job aggregator functionality."""

from unittest.mock import patch

import pytest

from slurm_monitor.job_aggregator import (
    JobAggregator,
    filter_jobs_by_state,
    get_job_by_id,
    merge_jobs,
    sort_jobs_by_time,
)
from slurm_monitor.squeue_parser import SlurmJob


class TestMergeJobs:
    """Test suite for merge_jobs function."""

    def test_merge_empty_lists(self):
        """Test merging two empty lists."""
        active = []
        historical = []

        result = merge_jobs(active, historical)

        assert result == []

    def test_merge_only_active_jobs(self):
        """Test merging with only active jobs."""
        active = [
            SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user"),
            SlurmJob("12346", "job2", "PENDING", "00:00:00", "/home/user"),
        ]
        historical = []

        result = merge_jobs(active, historical)

        assert len(result) == 2
        assert result[0].job_id == "12346"  # Sorted descending
        assert result[1].job_id == "12345"

    def test_merge_only_historical_jobs(self):
        """Test merging with only historical jobs."""
        active = []
        historical = [
            SlurmJob("12343", "job1", "COMPLETED", "01:23:45", "/home/user"),
            SlurmJob("12344", "job2", "FAILED", "00:05:30", "/home/user"),
        ]

        result = merge_jobs(active, historical)

        assert len(result) == 2
        assert result[0].job_id == "12344"  # Sorted descending
        assert result[1].job_id == "12343"

    def test_merge_no_duplicates(self):
        """Test merging active and historical jobs with no duplicates."""
        active = [
            SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user"),
        ]
        historical = [
            SlurmJob("12343", "job2", "COMPLETED", "02:34:56", "/home/user"),
            SlurmJob("12344", "job3", "FAILED", "00:05:30", "/home/user"),
        ]

        result = merge_jobs(active, historical)

        assert len(result) == 3
        assert result[0].job_id == "12345"  # Sorted descending
        assert result[1].job_id == "12344"
        assert result[2].job_id == "12343"

    def test_merge_with_duplicates_active_wins(self):
        """Test that active jobs take precedence over historical duplicates."""
        active = [
            SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user"),
        ]
        historical = [
            SlurmJob("12345", "job1", "PENDING", "00:00:00", "/home/user"),
            SlurmJob("12344", "job2", "COMPLETED", "02:34:56", "/home/user"),
        ]

        result = merge_jobs(active, historical)

        assert len(result) == 2
        # Job 12345 should have the state from active jobs
        job_12345 = next(job for job in result if job.job_id == "12345")
        assert job_12345.state == "RUNNING"  # From active, not PENDING
        assert job_12345.time == "01:23:45"  # From active

    def test_merge_multiple_duplicates(self):
        """Test merging with multiple duplicate job IDs."""
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
        # Both duplicates should use active job data
        job_12345 = next(job for job in result if job.job_id == "12345")
        job_12346 = next(job for job in result if job.job_id == "12346")
        assert job_12345.state == "RUNNING"
        assert job_12346.state == "RUNNING"

    def test_merge_preserves_all_fields(self):
        """Test that merge preserves all job fields correctly."""
        active = [
            SlurmJob(
                "12345",
                "my_job",
                "RUNNING",
                "01:23:45",
                "/home/user/project",
            ),
        ]
        historical = [
            SlurmJob("12344", "other_job", "COMPLETED", "02:34:56", "/home/user/other"),
        ]

        result = merge_jobs(active, historical)

        assert result[0].job_id == "12345"
        assert result[0].name == "my_job"
        assert result[0].state == "RUNNING"
        assert result[0].time == "01:23:45"
        assert result[0].work_dir == "/home/user/project"

        assert result[1].job_id == "12344"
        assert result[1].name == "other_job"

    def test_merge_sorted_descending_by_job_id(self):
        """Test that result is sorted by job ID in descending order."""
        active = [
            SlurmJob("12340", "job1", "RUNNING", "01:23:45", "/home/user"),
        ]
        historical = [
            SlurmJob("12350", "job2", "COMPLETED", "02:34:56", "/home/user"),
            SlurmJob("12345", "job3", "FAILED", "00:05:30", "/home/user"),
        ]

        result = merge_jobs(active, historical)

        assert len(result) == 3
        assert result[0].job_id == "12350"
        assert result[1].job_id == "12345"
        assert result[2].job_id == "12340"


class TestSortJobsByTime:
    """Test suite for sort_jobs_by_time function."""

    def test_sort_empty_list(self):
        """Test sorting empty list."""
        jobs = []

        result = sort_jobs_by_time(jobs)

        assert result == []

    def test_sort_single_job(self):
        """Test sorting single job."""
        jobs = [SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user")]

        result = sort_jobs_by_time(jobs)

        assert len(result) == 1
        assert result[0].job_id == "12345"

    def test_sort_descending_default(self):
        """Test default sorting is descending (longest time first)."""
        jobs = [
            SlurmJob("12345", "job1", "RUNNING", "00:30:00", "/home/user"),
            SlurmJob("12346", "job2", "RUNNING", "02:00:00", "/home/user"),
            SlurmJob("12347", "job3", "RUNNING", "01:00:00", "/home/user"),
        ]

        result = sort_jobs_by_time(jobs)

        assert result[0].time == "02:00:00"
        assert result[1].time == "01:00:00"
        assert result[2].time == "00:30:00"

    def test_sort_ascending(self):
        """Test ascending sort (shortest time first)."""
        jobs = [
            SlurmJob("12345", "job1", "RUNNING", "00:30:00", "/home/user"),
            SlurmJob("12346", "job2", "RUNNING", "02:00:00", "/home/user"),
            SlurmJob("12347", "job3", "RUNNING", "01:00:00", "/home/user"),
        ]

        result = sort_jobs_by_time(jobs, reverse=False)

        assert result[0].time == "00:30:00"
        assert result[1].time == "01:00:00"
        assert result[2].time == "02:00:00"


class TestFilterJobsByState:
    """Test suite for filter_jobs_by_state function."""

    def test_filter_empty_list(self):
        """Test filtering empty list."""
        jobs = []

        result = filter_jobs_by_state(jobs, ["RUNNING"])

        assert result == []

    def test_filter_single_state(self):
        """Test filtering by single state."""
        jobs = [
            SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user"),
            SlurmJob("12346", "job2", "PENDING", "00:00:00", "/home/user"),
            SlurmJob("12347", "job3", "COMPLETED", "02:34:56", "/home/user"),
        ]

        result = filter_jobs_by_state(jobs, ["RUNNING"])

        assert len(result) == 1
        assert result[0].job_id == "12345"
        assert result[0].state == "RUNNING"

    def test_filter_multiple_states(self):
        """Test filtering by multiple states."""
        jobs = [
            SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user"),
            SlurmJob("12346", "job2", "PENDING", "00:00:00", "/home/user"),
            SlurmJob("12347", "job3", "COMPLETED", "02:34:56", "/home/user"),
            SlurmJob("12348", "job4", "FAILED", "00:05:30", "/home/user"),
        ]

        result = filter_jobs_by_state(jobs, ["RUNNING", "PENDING"])

        assert len(result) == 2
        states = [job.state for job in result]
        assert "RUNNING" in states
        assert "PENDING" in states

    def test_filter_no_matches(self):
        """Test filtering with no matching states."""
        jobs = [
            SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user"),
            SlurmJob("12346", "job2", "PENDING", "00:00:00", "/home/user"),
        ]

        result = filter_jobs_by_state(jobs, ["COMPLETED", "FAILED"])

        assert result == []

    def test_filter_preserves_order(self):
        """Test that filtering preserves original order."""
        jobs = [
            SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user"),
            SlurmJob("12346", "job2", "RUNNING", "00:30:00", "/home/user"),
            SlurmJob("12347", "job3", "PENDING", "00:00:00", "/home/user"),
        ]

        result = filter_jobs_by_state(jobs, ["RUNNING"])

        assert len(result) == 2
        assert result[0].job_id == "12345"
        assert result[1].job_id == "12346"


class TestGetJobById:
    """Test suite for get_job_by_id function."""

    def test_get_from_empty_list(self):
        """Test getting job from empty list."""
        jobs = []

        result = get_job_by_id(jobs, "12345")

        assert result is None

    def test_get_existing_job(self):
        """Test getting existing job."""
        jobs = [
            SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user"),
            SlurmJob("12346", "job2", "PENDING", "00:00:00", "/home/user"),
        ]

        result = get_job_by_id(jobs, "12345")

        assert result is not None
        assert result.job_id == "12345"
        assert result.name == "job1"

    def test_get_nonexistent_job(self):
        """Test getting nonexistent job."""
        jobs = [
            SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user"),
        ]

        result = get_job_by_id(jobs, "99999")

        assert result is None

    def test_get_returns_first_match(self):
        """Test that function returns first matching job."""
        jobs = [
            SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user"),
            SlurmJob("12346", "job2", "PENDING", "00:00:00", "/home/user"),
            SlurmJob("12345", "job3", "COMPLETED", "02:34:56", "/home/user"),
        ]

        result = get_job_by_id(jobs, "12345")

        assert result is not None
        assert result.name == "job1"  # First match


class TestJobAggregator:
    """Test suite for JobAggregator class."""

    def test_aggregator_initialization(self):
        """Test JobAggregator initialization."""
        aggregator = JobAggregator("testhost", timeout=30)

        assert aggregator.host == "testhost"
        assert aggregator.timeout == 30

    def test_aggregator_default_timeout(self):
        """Test JobAggregator with default timeout."""
        aggregator = JobAggregator("testhost")

        assert aggregator.timeout == 10

    def test_fetch_all_jobs_success(self):
        """Test successful fetching and merging of all jobs."""
        active_mock = [
            SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user"),
        ]
        historical_mock = [
            SlurmJob("12344", "job2", "COMPLETED", "02:34:56", "/home/user"),
        ]

        with patch(
            "slurm_monitor.job_aggregator.fetch_squeue_jobs"
        ) as mock_squeue, patch(
            "slurm_monitor.job_aggregator.fetch_sacct_jobs"
        ) as mock_sacct:
            mock_squeue.return_value = active_mock
            mock_sacct.return_value = historical_mock

            aggregator = JobAggregator("testhost")
            result = aggregator.fetch_all_jobs()

            assert len(result) == 2
            assert result[0].job_id == "12345"  # Sorted descending
            assert result[1].job_id == "12344"

    def test_fetch_all_jobs_with_duplicates(self):
        """Test fetching with duplicate job IDs (active wins)."""
        active_mock = [
            SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user"),
        ]
        historical_mock = [
            SlurmJob("12345", "job1", "PENDING", "00:00:00", "/home/user"),
            SlurmJob("12344", "job2", "COMPLETED", "02:34:56", "/home/user"),
        ]

        with patch(
            "slurm_monitor.job_aggregator.fetch_squeue_jobs"
        ) as mock_squeue, patch(
            "slurm_monitor.job_aggregator.fetch_sacct_jobs"
        ) as mock_sacct:
            mock_squeue.return_value = active_mock
            mock_sacct.return_value = historical_mock

            aggregator = JobAggregator("testhost")
            result = aggregator.fetch_all_jobs()

            assert len(result) == 2
            job_12345 = next(job for job in result if job.job_id == "12345")
            assert job_12345.state == "RUNNING"  # Active state wins

    def test_fetch_all_jobs_empty_results(self):
        """Test fetching when no jobs exist."""
        with patch(
            "slurm_monitor.job_aggregator.fetch_squeue_jobs"
        ) as mock_squeue, patch(
            "slurm_monitor.job_aggregator.fetch_sacct_jobs"
        ) as mock_sacct:
            mock_squeue.return_value = []
            mock_sacct.return_value = []

            aggregator = JobAggregator("testhost")
            result = aggregator.fetch_all_jobs()

            assert result == []

    def test_fetch_all_jobs_passes_timeout(self):
        """Test that timeout is passed to fetch functions."""
        with patch(
            "slurm_monitor.job_aggregator.fetch_squeue_jobs"
        ) as mock_squeue, patch(
            "slurm_monitor.job_aggregator.fetch_sacct_jobs"
        ) as mock_sacct:
            mock_squeue.return_value = []
            mock_sacct.return_value = []

            aggregator = JobAggregator("testhost", timeout=30)
            aggregator.fetch_all_jobs()

            # Verify timeout was passed
            assert mock_squeue.call_args[1]["timeout"] == 30
            assert mock_sacct.call_args[1]["timeout"] == 30

    def test_fetch_all_jobs_calls_both_sources(self):
        """Test that both squeue and sacct are called."""
        with patch(
            "slurm_monitor.job_aggregator.fetch_squeue_jobs"
        ) as mock_squeue, patch(
            "slurm_monitor.job_aggregator.fetch_sacct_jobs"
        ) as mock_sacct:
            mock_squeue.return_value = []
            mock_sacct.return_value = []

            aggregator = JobAggregator("testhost")
            aggregator.fetch_all_jobs()

            mock_squeue.assert_called_once()
            mock_sacct.assert_called_once()
