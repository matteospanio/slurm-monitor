"""Tests for sacct parser functionality."""

from unittest.mock import MagicMock

import pytest

from slurmhub.config import SSHConfig
from slurmhub.sacct_parser import (
    fetch_sacct_jobs,
    jobs_to_dict_list,
    parse_sacct_line,
    parse_sacct_output,
)
from slurmhub.squeue_parser import SlurmJob
from slurmhub.ssh_wrapper import SSHClient


@pytest.fixture
def mock_ssh_client():
    client = MagicMock(spec=SSHClient)
    client.host = "testhost"
    return client


class TestParseSacctLine:
    """Test suite for parse_sacct_line function."""

    def test_parse_valid_line_with_workdir(self):
        line = "12345        my_job   COMPLETED   01:23:45   /home/user/project"
        job = parse_sacct_line(line)
        assert job is not None
        assert job.job_id == "12345"
        assert job.name == "my_job"
        assert job.state == "COMPLETED"
        assert job.time == "01:23:45"
        assert job.work_dir == "/home/user/project"

    def test_parse_valid_line_without_workdir(self):
        line = "12345   my_job   FAILED   00:05:30"
        job = parse_sacct_line(line)
        assert job is not None
        assert job.work_dir is None

    def test_parse_line_with_single_spaces(self):
        line = "12345 my_job RUNNING 1:23:45 /home/user"
        job = parse_sacct_line(line)
        assert job is not None
        assert job.job_id == "12345"

    def test_parse_line_with_tabs(self):
        line = "12345\tmy_job\tRUNNING\t1:23:45\t/home/user"
        job = parse_sacct_line(line)
        assert job is not None
        assert job.name == "my_job"

    def test_parse_empty_line(self):
        assert parse_sacct_line("") is None

    def test_parse_whitespace_only_line(self):
        assert parse_sacct_line("   \t  \n") is None

    def test_parse_invalid_line_too_few_fields(self):
        assert parse_sacct_line("12345 my_job RUNNING") is None

    def test_parse_line_with_special_characters_in_name(self):
        line = "12345   my-job_test.v2   COMPLETED   01:23:45   /home/user"
        job = parse_sacct_line(line)
        assert job is not None
        assert job.name == "my-job_test.v2"

    def test_parse_line_different_states(self):
        for state in ["COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY"]:
            line = f"12345   my_job   {state}   01:23:45   /home/user"
            job = parse_sacct_line(line)
            assert job is not None
            assert job.state == state

    def test_parse_line_with_long_workdir(self):
        line = "12345   my_job   COMPLETED   01:23:45   /home/user/very/long/path/to/project"
        job = parse_sacct_line(line)
        assert job.work_dir == "/home/user/very/long/path/to/project"

    def test_parse_line_with_leading_trailing_spaces(self):
        line = "   12345   my_job   COMPLETED   01:23:45   /home/user   "
        job = parse_sacct_line(line)
        assert job is not None
        assert job.job_id == "12345"


class TestParseSacctOutput:
    """Test suite for parse_sacct_output function."""

    def test_parse_empty_output(self):
        assert parse_sacct_output("") == []

    def test_parse_whitespace_output(self):
        assert parse_sacct_output("   \n\n   ") == []

    def test_parse_single_job(self):
        output = "12345   my_job   COMPLETED   01:23:45   /home/user/project"
        jobs = parse_sacct_output(output)
        assert len(jobs) == 1

    def test_parse_multiple_jobs(self):
        output = """12345   job1   COMPLETED   01:23:45   /home/user/project1
12346   job2   FAILED      00:05:30   /home/user/project2
12347   job3   CANCELLED   02:34:56   /home/user/project3"""
        jobs = parse_sacct_output(output)
        assert len(jobs) == 3

    def test_parse_output_with_empty_lines(self):
        output = """12345   job1   COMPLETED   01:23:45   /home/user

12346   job2   FAILED   00:05:30   /home/user
"""
        jobs = parse_sacct_output(output)
        assert len(jobs) == 2

    def test_parse_output_skips_malformed_lines(self):
        output = """12345   job1   COMPLETED   01:23:45   /home/user
invalid line
12346   job2   FAILED   00:05:30   /home/user"""
        jobs = parse_sacct_output(output)
        assert len(jobs) == 2


class TestJobsToDictList:
    """Test suite for jobs_to_dict_list function."""

    def test_convert_empty_list(self):
        assert jobs_to_dict_list([]) == []

    def test_convert_single_job(self):
        jobs = [SlurmJob("12345", "my_job", "COMPLETED", "01:23:45", "/home/user")]
        result = jobs_to_dict_list(jobs)
        assert len(result) == 1
        assert result[0]["state"] == "COMPLETED"

    def test_convert_multiple_jobs(self):
        jobs = [
            SlurmJob("12345", "job1", "COMPLETED", "01:23:45"),
            SlurmJob("12346", "job2", "FAILED", "00:05:30"),
        ]
        result = jobs_to_dict_list(jobs)
        assert len(result) == 2


class TestFetchSacctJobs:
    """Test suite for fetch_sacct_jobs function."""

    def test_fetch_jobs_success(self, mock_ssh_client):
        mock_ssh_client.execute.return_value = (
            "12345   job1   COMPLETED   01:23:45   /home/user/project1\n"
            "12346   job2   FAILED   00:05:30   /home/user/project2"
        )
        jobs = fetch_sacct_jobs(mock_ssh_client)
        assert len(jobs) == 2
        assert jobs[0].job_id == "12345"

    def test_fetch_jobs_correct_command(self, mock_ssh_client):
        mock_ssh_client.execute.return_value = ""
        fetch_sacct_jobs(mock_ssh_client)
        cmd = mock_ssh_client.execute.call_args[0][0]
        assert "sacct -X --format=JobID,JobName,State,Elapsed,WorkDir --units=M -n" == cmd

    def test_fetch_jobs_custom_timeout(self, mock_ssh_client):
        mock_ssh_client.execute.return_value = ""
        fetch_sacct_jobs(mock_ssh_client, timeout=30)
        assert mock_ssh_client.execute.call_args[0][1] == 30

    def test_fetch_jobs_custom_format(self, mock_ssh_client):
        mock_ssh_client.execute.return_value = ""
        fetch_sacct_jobs(mock_ssh_client, format_fields="JobID,JobName,State")
        cmd = mock_ssh_client.execute.call_args[0][0]
        assert "JobID,JobName,State" in cmd

    def test_fetch_jobs_empty_output(self, mock_ssh_client):
        mock_ssh_client.execute.return_value = ""
        assert fetch_sacct_jobs(mock_ssh_client) == []

    def test_fetch_jobs_various_states(self, mock_ssh_client):
        mock_ssh_client.execute.return_value = (
            "12345   job1   COMPLETED     01:23:45   /home/user\n"
            "12346   job2   FAILED        00:05:30   /home/user\n"
            "12347   job3   CANCELLED     02:34:56   /home/user\n"
            "12348   job4   TIMEOUT       00:10:00   /home/user\n"
            "12349   job5   OUT_OF_MEMORY 00:02:15   /home/user"
        )
        jobs = fetch_sacct_jobs(mock_ssh_client)
        assert len(jobs) == 5
        states = [j.state for j in jobs]
        assert "COMPLETED" in states
        assert "FAILED" in states
        assert "TIMEOUT" in states
