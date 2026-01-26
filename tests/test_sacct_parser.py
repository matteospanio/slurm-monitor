"""Tests for sacct parser functionality."""

from unittest.mock import patch

import pytest

from slurm_monitor.sacct_parser import (
    fetch_sacct_jobs,
    jobs_to_dict_list,
    parse_sacct_line,
    parse_sacct_output,
)
from slurm_monitor.squeue_parser import SlurmJob


class TestParseSacctLine:
    """Test suite for parse_sacct_line function."""

    def test_parse_valid_line_with_workdir(self):
        """Test parsing a valid sacct line with all fields."""
        line = "12345        my_job   COMPLETED   01:23:45   /home/user/project"

        job = parse_sacct_line(line)

        assert job is not None
        assert job.job_id == "12345"
        assert job.name == "my_job"
        assert job.state == "COMPLETED"
        assert job.time == "01:23:45"
        assert job.work_dir == "/home/user/project"

    def test_parse_valid_line_without_workdir(self):
        """Test parsing a valid sacct line without workdir."""
        line = "12345   my_job   FAILED   00:05:30"

        job = parse_sacct_line(line)

        assert job is not None
        assert job.job_id == "12345"
        assert job.name == "my_job"
        assert job.state == "FAILED"
        assert job.time == "00:05:30"
        assert job.work_dir is None

    def test_parse_line_with_single_spaces(self):
        """Test parsing line with single spaces between fields."""
        line = "12345 my_job RUNNING 1:23:45 /home/user"

        job = parse_sacct_line(line)

        assert job is not None
        assert job.job_id == "12345"
        assert job.name == "my_job"
        assert job.state == "RUNNING"

    def test_parse_line_with_tabs(self):
        """Test parsing line with tab separators."""
        line = "12345\tmy_job\tRUNNING\t1:23:45\t/home/user"

        job = parse_sacct_line(line)

        assert job is not None
        assert job.job_id == "12345"
        assert job.name == "my_job"

    def test_parse_empty_line(self):
        """Test that empty line returns None."""
        line = ""

        job = parse_sacct_line(line)

        assert job is None

    def test_parse_whitespace_only_line(self):
        """Test that whitespace-only line returns None."""
        line = "   \t  \n"

        job = parse_sacct_line(line)

        assert job is None

    def test_parse_invalid_line_too_few_fields(self):
        """Test that invalid line with too few fields returns None."""
        line = "12345 my_job RUNNING"

        job = parse_sacct_line(line)

        assert job is None

    def test_parse_line_with_special_characters_in_name(self):
        """Test parsing line with special characters in job name."""
        line = "12345   my-job_test.v2   COMPLETED   01:23:45   /home/user"

        job = parse_sacct_line(line)

        assert job is not None
        assert job.name == "my-job_test.v2"

    def test_parse_line_different_states(self):
        """Test parsing lines with different job states."""
        states = [
            "COMPLETED",
            "FAILED",
            "CANCELLED",
            "TIMEOUT",
            "OUT_OF_MEMORY",
        ]

        for state in states:
            line = f"12345   my_job   {state}   01:23:45   /home/user"
            job = parse_sacct_line(line)
            assert job is not None
            assert job.state == state

    def test_parse_line_with_long_workdir(self):
        """Test parsing line with a long workdir path."""
        line = "12345   my_job   COMPLETED   01:23:45   /home/user/very/long/path/to/project/directory"

        job = parse_sacct_line(line)

        assert job is not None
        assert (
            job.work_dir
            == "/home/user/very/long/path/to/project/directory"
        )

    def test_parse_line_with_leading_trailing_spaces(self):
        """Test parsing line with leading/trailing spaces."""
        line = "   12345   my_job   COMPLETED   01:23:45   /home/user   "

        job = parse_sacct_line(line)

        assert job is not None
        assert job.job_id == "12345"

    def test_parse_line_realistic_sacct_format(self):
        """Test parsing line with realistic sacct formatting."""
        # Sacct typically formats with fixed-width columns
        line = "12345              my_job  COMPLETED  01:23:45  /home/user/project"

        job = parse_sacct_line(line)

        assert job is not None
        assert job.job_id == "12345"
        assert job.name == "my_job"
        assert job.state == "COMPLETED"


class TestParseSacctOutput:
    """Test suite for parse_sacct_output function."""

    def test_parse_empty_output(self):
        """Test parsing empty output returns empty list."""
        output = ""

        jobs = parse_sacct_output(output)

        assert jobs == []

    def test_parse_whitespace_output(self):
        """Test parsing whitespace-only output returns empty list."""
        output = "   \n\n   "

        jobs = parse_sacct_output(output)

        assert jobs == []

    def test_parse_single_job(self):
        """Test parsing output with single job."""
        output = "12345   my_job   COMPLETED   01:23:45   /home/user/project"

        jobs = parse_sacct_output(output)

        assert len(jobs) == 1
        assert jobs[0].job_id == "12345"
        assert jobs[0].name == "my_job"

    def test_parse_multiple_jobs(self):
        """Test parsing output with multiple jobs."""
        output = """12345   job1   COMPLETED   01:23:45   /home/user/project1
12346   job2   FAILED      00:05:30   /home/user/project2
12347   job3   CANCELLED   02:34:56   /home/user/project3"""

        jobs = parse_sacct_output(output)

        assert len(jobs) == 3
        assert jobs[0].job_id == "12345"
        assert jobs[1].job_id == "12346"
        assert jobs[2].job_id == "12347"

    def test_parse_output_with_empty_lines(self):
        """Test parsing output with empty lines."""
        output = """12345   job1   COMPLETED   01:23:45   /home/user/project1

12346   job2   FAILED   00:05:30   /home/user/project2
"""

        jobs = parse_sacct_output(output)

        assert len(jobs) == 2

    def test_parse_output_skips_malformed_lines(self):
        """Test that malformed lines are skipped."""
        output = """12345   job1   COMPLETED   01:23:45   /home/user/project1
invalid line
12346   job2   FAILED   00:05:30   /home/user/project2"""

        jobs = parse_sacct_output(output)

        assert len(jobs) == 2
        assert jobs[0].job_id == "12345"
        assert jobs[1].job_id == "12346"

    def test_parse_realistic_sacct_output(self):
        """Test parsing realistic sacct output with fixed-width columns."""
        output = """12345              my_job  COMPLETED  01:23:45  /home/user/project
12346         another_job     FAILED  00:05:30  /home/user/other
12347          third_job  CANCELLED  02:34:56  /home/user/another"""

        jobs = parse_sacct_output(output)

        assert len(jobs) == 3
        assert jobs[0].state == "COMPLETED"
        assert jobs[1].state == "FAILED"
        assert jobs[2].state == "CANCELLED"


class TestJobsToDictList:
    """Test suite for jobs_to_dict_list function."""

    def test_convert_empty_list(self):
        """Test converting empty list."""
        jobs = []

        result = jobs_to_dict_list(jobs)

        assert result == []

    def test_convert_single_job(self):
        """Test converting single job."""
        jobs = [
            SlurmJob(
                job_id="12345",
                name="my_job",
                state="COMPLETED",
                time="01:23:45",
                work_dir="/home/user",
            )
        ]

        result = jobs_to_dict_list(jobs)

        assert len(result) == 1
        assert result[0]["job_id"] == "12345"
        assert result[0]["state"] == "COMPLETED"

    def test_convert_multiple_jobs(self):
        """Test converting multiple jobs."""
        jobs = [
            SlurmJob("12345", "job1", "COMPLETED", "01:23:45", "/home/user"),
            SlurmJob("12346", "job2", "FAILED", "00:05:30"),
        ]

        result = jobs_to_dict_list(jobs)

        assert len(result) == 2
        assert result[0]["job_id"] == "12345"
        assert result[1]["job_id"] == "12346"


class TestFetchSacctJobs:
    """Test suite for fetch_sacct_jobs function."""

    def test_fetch_jobs_success(self):
        """Test successful fetching and parsing of jobs."""
        mock_output = """12345   job1   COMPLETED   01:23:45   /home/user/project1
12346   job2   FAILED   00:05:30   /home/user/project2"""

        with patch(
            "slurm_monitor.sacct_parser.execute_ssh_command"
        ) as mock_ssh:
            mock_ssh.return_value = mock_output

            jobs = fetch_sacct_jobs("testhost")

            assert len(jobs) == 2
            assert jobs[0].job_id == "12345"
            assert jobs[1].job_id == "12346"
            mock_ssh.assert_called_once()

    def test_fetch_jobs_correct_command(self):
        """Test that correct sacct command is executed."""
        with patch(
            "slurm_monitor.sacct_parser.execute_ssh_command"
        ) as mock_ssh:
            mock_ssh.return_value = ""

            fetch_sacct_jobs("testhost")

            args = mock_ssh.call_args[0]
            assert args[0] == "testhost"
            assert (
                "sacct -X --format=JobID,JobName,State,Elapsed,WorkDir --units=M -n"
                in args[1]
            )

    def test_fetch_jobs_custom_timeout(self):
        """Test using custom timeout."""
        with patch(
            "slurm_monitor.sacct_parser.execute_ssh_command"
        ) as mock_ssh:
            mock_ssh.return_value = ""

            fetch_sacct_jobs("testhost", timeout=30)

            # Check that timeout was passed as positional arg (3rd argument)
            assert mock_ssh.call_args[0][2] == 30

    def test_fetch_jobs_custom_format(self):
        """Test using custom format fields."""
        with patch(
            "slurm_monitor.sacct_parser.execute_ssh_command"
        ) as mock_ssh:
            mock_ssh.return_value = ""

            fetch_sacct_jobs("testhost", format_fields="JobID,JobName,State")

            args = mock_ssh.call_args[0]
            assert "sacct -X --format=JobID,JobName,State --units=M -n" in args[1]

    def test_fetch_jobs_empty_output(self):
        """Test fetching when no historical jobs exist."""
        with patch(
            "slurm_monitor.sacct_parser.execute_ssh_command"
        ) as mock_ssh:
            mock_ssh.return_value = ""

            jobs = fetch_sacct_jobs("testhost")

            assert jobs == []

    def test_fetch_jobs_returns_json_structure(self):
        """Test that fetched jobs can be converted to JSON structure."""
        mock_output = "12345   job1   COMPLETED   01:23:45   /home/user/project1"

        with patch(
            "slurm_monitor.sacct_parser.execute_ssh_command"
        ) as mock_ssh:
            mock_ssh.return_value = mock_output

            jobs = fetch_sacct_jobs("testhost")
            jobs_dict = jobs_to_dict_list(jobs)

            assert isinstance(jobs_dict, list)
            assert isinstance(jobs_dict[0], dict)
            assert "job_id" in jobs_dict[0]
            assert "name" in jobs_dict[0]
            assert "state" in jobs_dict[0]
            assert jobs_dict[0]["state"] == "COMPLETED"

    def test_fetch_jobs_handles_various_states(self):
        """Test fetching jobs with various historical states."""
        mock_output = """12345   job1   COMPLETED     01:23:45   /home/user
12346   job2   FAILED        00:05:30   /home/user
12347   job3   CANCELLED     02:34:56   /home/user
12348   job4   TIMEOUT       00:10:00   /home/user
12349   job5   OUT_OF_MEMORY 00:02:15   /home/user"""

        with patch(
            "slurm_monitor.sacct_parser.execute_ssh_command"
        ) as mock_ssh:
            mock_ssh.return_value = mock_output

            jobs = fetch_sacct_jobs("testhost")

            assert len(jobs) == 5
            states = [job.state for job in jobs]
            assert "COMPLETED" in states
            assert "FAILED" in states
            assert "CANCELLED" in states
            assert "TIMEOUT" in states
            assert "OUT_OF_MEMORY" in states
