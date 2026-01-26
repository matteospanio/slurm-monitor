"""Tests for squeue parser functionality."""

from unittest.mock import patch

import pytest

from slurm_monitor.squeue_parser import (
    SlurmJob,
    fetch_squeue_jobs,
    jobs_to_dict_list,
    parse_squeue_line,
    parse_squeue_output,
)


class TestParseSqueueLine:
    """Test suite for parse_squeue_line function."""

    def test_parse_valid_line_with_workdir(self):
        """Test parsing a valid squeue line with all fields."""
        line = "12345|my_job|RUNNING|1:23:45|/home/user/project"

        job = parse_squeue_line(line)

        assert job.job_id == "12345"
        assert job.name == "my_job"
        assert job.state == "RUNNING"
        assert job.time == "1:23:45"
        assert job.work_dir == "/home/user/project"

    def test_parse_valid_line_without_workdir(self):
        """Test parsing a valid squeue line without workdir."""
        line = "12345|my_job|PENDING|0:00:00"

        job = parse_squeue_line(line)

        assert job.job_id == "12345"
        assert job.name == "my_job"
        assert job.state == "PENDING"
        assert job.time == "0:00:00"
        assert job.work_dir is None

    def test_parse_line_with_empty_workdir(self):
        """Test parsing line with empty workdir field."""
        line = "12345|my_job|RUNNING|1:23:45|"

        job = parse_squeue_line(line)

        assert job.job_id == "12345"
        assert job.work_dir is None

    def test_parse_line_with_spaces(self):
        """Test parsing line with leading/trailing spaces."""
        line = "  12345|my_job|RUNNING|1:23:45|/home/user  "

        job = parse_squeue_line(line)

        assert job.job_id == "12345"
        # Strip removes trailing spaces from the line, not individual fields
        assert job.work_dir == "/home/user"

    def test_parse_invalid_line_too_few_fields(self):
        """Test that invalid line with too few fields raises ValueError."""
        line = "12345|my_job|RUNNING"

        with pytest.raises(ValueError) as exc_info:
            parse_squeue_line(line)

        assert "Invalid squeue line format" in str(exc_info.value)
        assert "Expected at least 4 fields" in str(exc_info.value)

    def test_parse_line_with_special_characters(self):
        """Test parsing line with special characters in job name."""
        line = "12345|my-job_test.v2|RUNNING|1:23:45|/home/user"

        job = parse_squeue_line(line)

        assert job.name == "my-job_test.v2"

    def test_parse_line_different_states(self):
        """Test parsing lines with different job states."""
        states = ["RUNNING", "PENDING", "COMPLETED", "FAILED", "CANCELLED"]

        for state in states:
            line = f"12345|my_job|{state}|1:23:45|/home/user"
            job = parse_squeue_line(line)
            assert job.state == state


class TestParseSqueueOutput:
    """Test suite for parse_squeue_output function."""

    def test_parse_empty_output(self):
        """Test parsing empty output returns empty list."""
        output = ""

        jobs = parse_squeue_output(output)

        assert jobs == []

    def test_parse_whitespace_output(self):
        """Test parsing whitespace-only output returns empty list."""
        output = "   \n\n   "

        jobs = parse_squeue_output(output)

        assert jobs == []

    def test_parse_single_job(self):
        """Test parsing output with single job."""
        output = "12345|my_job|RUNNING|1:23:45|/home/user/project"

        jobs = parse_squeue_output(output)

        assert len(jobs) == 1
        assert jobs[0].job_id == "12345"
        assert jobs[0].name == "my_job"

    def test_parse_multiple_jobs(self):
        """Test parsing output with multiple jobs."""
        output = """12345|job1|RUNNING|1:23:45|/home/user/project1
12346|job2|PENDING|0:00:00|/home/user/project2
12347|job3|RUNNING|2:34:56|/home/user/project3"""

        jobs = parse_squeue_output(output)

        assert len(jobs) == 3
        assert jobs[0].job_id == "12345"
        assert jobs[1].job_id == "12346"
        assert jobs[2].job_id == "12347"

    def test_parse_output_with_empty_lines(self):
        """Test parsing output with empty lines."""
        output = """12345|job1|RUNNING|1:23:45|/home/user/project1

12346|job2|PENDING|0:00:00|/home/user/project2
"""

        jobs = parse_squeue_output(output)

        assert len(jobs) == 2

    def test_parse_output_skips_malformed_lines(self):
        """Test that malformed lines are skipped."""
        output = """12345|job1|RUNNING|1:23:45|/home/user/project1
invalid line
12346|job2|PENDING|0:00:00|/home/user/project2"""

        jobs = parse_squeue_output(output)

        assert len(jobs) == 2
        assert jobs[0].job_id == "12345"
        assert jobs[1].job_id == "12346"


class TestSlurmJob:
    """Test suite for SlurmJob dataclass."""

    def test_job_to_dict(self):
        """Test converting job to dictionary."""
        job = SlurmJob(
            job_id="12345",
            name="my_job",
            state="RUNNING",
            time="1:23:45",
            work_dir="/home/user/project",
        )

        job_dict = job.to_dict()

        assert job_dict == {
            "job_id": "12345",
            "name": "my_job",
            "state": "RUNNING",
            "time": "1:23:45",
            "work_dir": "/home/user/project",
        }

    def test_job_to_dict_without_workdir(self):
        """Test converting job without workdir to dictionary."""
        job = SlurmJob(
            job_id="12345",
            name="my_job",
            state="PENDING",
            time="0:00:00",
        )

        job_dict = job.to_dict()

        assert job_dict["work_dir"] is None


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
                state="RUNNING",
                time="1:23:45",
                work_dir="/home/user",
            )
        ]

        result = jobs_to_dict_list(jobs)

        assert len(result) == 1
        assert result[0]["job_id"] == "12345"

    def test_convert_multiple_jobs(self):
        """Test converting multiple jobs."""
        jobs = [
            SlurmJob("12345", "job1", "RUNNING", "1:23:45", "/home/user"),
            SlurmJob("12346", "job2", "PENDING", "0:00:00"),
        ]

        result = jobs_to_dict_list(jobs)

        assert len(result) == 2
        assert result[0]["job_id"] == "12345"
        assert result[1]["job_id"] == "12346"


class TestFetchSqueueJobs:
    """Test suite for fetch_squeue_jobs function."""

    def test_fetch_jobs_success(self):
        """Test successful fetching and parsing of jobs."""
        mock_output = """12345|job1|RUNNING|1:23:45|/home/user/project1
12346|job2|PENDING|0:00:00|/home/user/project2"""

        with patch(
            "slurm_monitor.squeue_parser.execute_ssh_command"
        ) as mock_ssh:
            mock_ssh.return_value = mock_output

            jobs = fetch_squeue_jobs("testhost")

            assert len(jobs) == 2
            assert jobs[0].job_id == "12345"
            assert jobs[1].job_id == "12346"
            mock_ssh.assert_called_once()

    def test_fetch_jobs_correct_command(self):
        """Test that correct squeue command is executed."""
        with patch(
            "slurm_monitor.squeue_parser.execute_ssh_command"
        ) as mock_ssh:
            mock_ssh.return_value = ""

            fetch_squeue_jobs("testhost")

            args = mock_ssh.call_args[0]
            assert args[0] == "testhost"
            assert 'squeue --me -o "%i|%j|%T|%M|%Z" --noheader' in args[1]

    def test_fetch_jobs_custom_timeout(self):
        """Test using custom timeout."""
        with patch(
            "slurm_monitor.squeue_parser.execute_ssh_command"
        ) as mock_ssh:
            mock_ssh.return_value = ""

            fetch_squeue_jobs("testhost", timeout=30)

            # Check that timeout was passed as positional arg (3rd argument)
            assert mock_ssh.call_args[0][2] == 30

    def test_fetch_jobs_custom_format(self):
        """Test using custom format string."""
        with patch(
            "slurm_monitor.squeue_parser.execute_ssh_command"
        ) as mock_ssh:
            mock_ssh.return_value = ""

            fetch_squeue_jobs("testhost", format_string="%i|%j|%T|%M")

            args = mock_ssh.call_args[0]
            assert 'squeue --me -o "%i|%j|%T|%M" --noheader' in args[1]

    def test_fetch_jobs_empty_output(self):
        """Test fetching when no jobs are running."""
        with patch(
            "slurm_monitor.squeue_parser.execute_ssh_command"
        ) as mock_ssh:
            mock_ssh.return_value = ""

            jobs = fetch_squeue_jobs("testhost")

            assert jobs == []

    def test_fetch_jobs_returns_json_structure(self):
        """Test that fetched jobs can be converted to JSON structure."""
        mock_output = "12345|job1|RUNNING|1:23:45|/home/user/project1"

        with patch(
            "slurm_monitor.squeue_parser.execute_ssh_command"
        ) as mock_ssh:
            mock_ssh.return_value = mock_output

            jobs = fetch_squeue_jobs("testhost")
            jobs_dict = jobs_to_dict_list(jobs)

            assert isinstance(jobs_dict, list)
            assert isinstance(jobs_dict[0], dict)
            assert "job_id" in jobs_dict[0]
            assert "name" in jobs_dict[0]
            assert "state" in jobs_dict[0]
