"""Tests for squeue parser functionality."""

from unittest.mock import MagicMock, patch

import pytest

from slurmhub.config import SSHConfig
from slurmhub.slurm.squeue import (
    SlurmJob,
    fetch_squeue_jobs,
    jobs_to_dict_list,
    parse_squeue_line,
    parse_squeue_output,
)
from slurmhub.slurm.ssh import SSHClient


@pytest.fixture
def mock_ssh_client():
    client = MagicMock(spec=SSHClient)
    client.host = "testhost"
    return client


class TestParseSqueueLine:
    """Test suite for parse_squeue_line function."""

    def test_parse_valid_line_with_workdir(self):
        line = "12345|my_job|RUNNING|1:23:45|/home/user/project"
        job = parse_squeue_line(line)
        assert job.job_id == "12345"
        assert job.name == "my_job"
        assert job.state == "RUNNING"
        assert job.time == "1:23:45"
        assert job.work_dir == "/home/user/project"

    def test_parse_valid_line_without_workdir(self):
        line = "12345|my_job|PENDING|0:00:00"
        job = parse_squeue_line(line)
        assert job.job_id == "12345"
        assert job.work_dir is None

    def test_parse_line_with_empty_workdir(self):
        line = "12345|my_job|RUNNING|1:23:45|"
        job = parse_squeue_line(line)
        assert job.work_dir is None

    def test_parse_line_with_spaces(self):
        line = "  12345|my_job|RUNNING|1:23:45|/home/user  "
        job = parse_squeue_line(line)
        assert job.job_id == "12345"
        assert job.work_dir == "/home/user"

    def test_parse_invalid_line_too_few_fields(self):
        with pytest.raises(ValueError, match="Invalid squeue line format"):
            parse_squeue_line("12345|my_job|RUNNING")

    def test_parse_line_with_special_characters(self):
        line = "12345|my-job_test.v2|RUNNING|1:23:45|/home/user"
        job = parse_squeue_line(line)
        assert job.name == "my-job_test.v2"

    def test_parse_line_different_states(self):
        for state in ["RUNNING", "PENDING", "COMPLETED", "FAILED", "CANCELLED"]:
            line = f"12345|my_job|{state}|1:23:45|/home/user"
            job = parse_squeue_line(line)
            assert job.state == state


class TestParseSqueueOutput:
    """Test suite for parse_squeue_output function."""

    def test_parse_empty_output(self):
        assert parse_squeue_output("") == []

    def test_parse_whitespace_output(self):
        assert parse_squeue_output("   \n\n   ") == []

    def test_parse_single_job(self):
        output = "12345|my_job|RUNNING|1:23:45|/home/user/project"
        jobs = parse_squeue_output(output)
        assert len(jobs) == 1
        assert jobs[0].job_id == "12345"

    def test_parse_multiple_jobs(self):
        output = """12345|job1|RUNNING|1:23:45|/home/user/project1
12346|job2|PENDING|0:00:00|/home/user/project2
12347|job3|RUNNING|2:34:56|/home/user/project3"""
        jobs = parse_squeue_output(output)
        assert len(jobs) == 3

    def test_parse_output_with_empty_lines(self):
        output = "12345|job1|RUNNING|1:23:45|/home/user\n\n12346|job2|PENDING|0:00:00|/home/user\n"
        jobs = parse_squeue_output(output)
        assert len(jobs) == 2

    def test_parse_output_skips_malformed_lines(self):
        output = """12345|job1|RUNNING|1:23:45|/home/user
invalid line
12346|job2|PENDING|0:00:00|/home/user"""
        jobs = parse_squeue_output(output)
        assert len(jobs) == 2


class TestSlurmJob:
    """Test suite for SlurmJob dataclass."""

    def test_job_to_dict(self):
        job = SlurmJob("12345", "my_job", "RUNNING", "1:23:45", "/home/user")
        assert job.to_dict() == {
            "job_id": "12345",
            "name": "my_job",
            "state": "RUNNING",
            "time": "1:23:45",
            "work_dir": "/home/user",
            "gres": None,
        }

    def test_job_to_dict_without_workdir(self):
        job = SlurmJob("12345", "my_job", "PENDING", "0:00:00")
        assert job.to_dict()["work_dir"] is None

    def test_gpu_display_typed(self):
        job = SlurmJob("1", "j", "R", "0:00", gres="gpu:l40s:4")
        assert job.gpu_display == "4x l40s"

    def test_gpu_display_generic(self):
        job = SlurmJob("1", "j", "R", "0:00", gres="gpu:2")
        assert job.gpu_display == "2x gpu"

    def test_gpu_display_none(self):
        job = SlurmJob("1", "j", "R", "0:00", gres=None)
        assert job.gpu_display == ""

    def test_gpu_display_null_string(self):
        job = SlurmJob("1", "j", "R", "0:00", gres="(null)")
        assert job.gpu_display == ""

    def test_parse_line_with_gres(self):
        line = "12345|my_job|RUNNING|1:00:00|/home/user|gpu:l40s:4"
        job = parse_squeue_line(line)
        assert job.gres == "gpu:l40s:4"
        assert job.gpu_display == "4x l40s"

    def test_parse_line_without_gres(self):
        line = "12345|my_job|RUNNING|1:00:00|/home/user"
        job = parse_squeue_line(line)
        assert job.gres is None


class TestJobsToDictList:
    """Test suite for jobs_to_dict_list function."""

    def test_convert_empty_list(self):
        assert jobs_to_dict_list([]) == []

    def test_convert_single_job(self):
        jobs = [SlurmJob("12345", "my_job", "RUNNING", "1:23:45", "/home/user")]
        result = jobs_to_dict_list(jobs)
        assert len(result) == 1
        assert result[0]["job_id"] == "12345"

    def test_convert_multiple_jobs(self):
        jobs = [
            SlurmJob("12345", "job1", "RUNNING", "1:23:45", "/home/user"),
            SlurmJob("12346", "job2", "PENDING", "0:00:00"),
        ]
        result = jobs_to_dict_list(jobs)
        assert len(result) == 2


class TestFetchSqueueJobs:
    """Test suite for fetch_squeue_jobs function."""

    def test_fetch_jobs_success(self, mock_ssh_client):
        mock_ssh_client.execute.return_value = (
            "12345|job1|RUNNING|1:23:45|/home/user/project1\n"
            "12346|job2|PENDING|0:00:00|/home/user/project2"
        )
        jobs = fetch_squeue_jobs(mock_ssh_client)
        assert len(jobs) == 2
        assert jobs[0].job_id == "12345"

    def test_fetch_jobs_correct_command(self, mock_ssh_client):
        mock_ssh_client.execute.return_value = ""
        fetch_squeue_jobs(mock_ssh_client)
        cmd = mock_ssh_client.execute.call_args[0][0]
        assert 'squeue --me -o "%i|%j|%T|%M|%Z|%b|%V|%C|%m" --noheader' == cmd

    def test_fetch_jobs_custom_timeout(self, mock_ssh_client):
        mock_ssh_client.execute.return_value = ""
        fetch_squeue_jobs(mock_ssh_client, timeout=30)
        assert mock_ssh_client.execute.call_args[0][1] == 30

    def test_fetch_jobs_custom_format(self, mock_ssh_client):
        mock_ssh_client.execute.return_value = ""
        fetch_squeue_jobs(mock_ssh_client, format_string="%i|%j|%T|%M")
        cmd = mock_ssh_client.execute.call_args[0][0]
        assert "%i|%j|%T|%M" in cmd

    def test_fetch_jobs_empty_output(self, mock_ssh_client):
        mock_ssh_client.execute.return_value = ""
        assert fetch_squeue_jobs(mock_ssh_client) == []

    def test_fetch_jobs_returns_json_structure(self, mock_ssh_client):
        mock_ssh_client.execute.return_value = (
            "12345|job1|RUNNING|1:23:45|/home/user"
        )
        jobs = fetch_squeue_jobs(mock_ssh_client)
        jobs_dict = jobs_to_dict_list(jobs)
        assert isinstance(jobs_dict, list)
        assert "job_id" in jobs_dict[0]
