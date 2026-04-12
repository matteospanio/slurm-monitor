"""Tests for scontrol parser and JobDetails."""

from unittest.mock import MagicMock, patch

import pytest

from slurm_monitor.config import SSHConfig
from slurm_monitor.scontrol_parser import (
    JobDetails,
    build_job_details,
    fetch_job_details,
    format_mem_human,
    parse_mem_bytes,
    parse_scontrol_output,
    parse_tres_mem,
)
from slurm_monitor.ssh_wrapper import SSHClient, SSHConnectionError

SCONTROL_OUTPUT = """\
JobId=4138646 JobName=bert-20k-preprocess_all
   UserId=spanio(15268) GroupId=collab(199) MCS_label=N/A
   Priority=32288 Nice=0 Account=dei QOS=allgroups_qos
   JobState=RUNNING Reason=None Dependency=(null)
   Requeue=1 Restarts=0 BatchFlag=1 Reboot=0 ExitCode=0:0
   RunTime=3-03:54:07 TimeLimit=9-04:00:00 TimeMin=N/A
   SubmitTime=2026-04-09T11:20:08 EligibleTime=2026-04-09T11:20:08
   AccrueTime=2026-04-09T11:20:08
   StartTime=2026-04-09T12:09:27 EndTime=2026-04-18T16:09:27 Deadline=N/A
   Partition=allgroups AllocNode:Sid=login:75247
   NodeList=runner-01
   NumNodes=1 NumCPUs=12 NumTasks=1 CPUs/Task=12
   ReqTRES=cpu=12,mem=512G,node=1,billing=12
   AllocTRES=cpu=12,mem=512G,node=1,billing=12
   Command=/home/spanio/jobs/tmp/mxlGPT/scripts/unipd_preprocess.sh
   WorkDir=/home/spanio/jobs/tmp/mxlGPT
   StdErr=/home/spanio/jobs/tmp/mxlGPT/logs/preprocess_all_4138646.err
   StdOut=/home/spanio/jobs/tmp/mxlGPT/logs/preprocess_all_4138646.out"""


class TestParseScontrolOutput:
    def test_parses_real_output(self):
        data = parse_scontrol_output(SCONTROL_OUTPUT)
        assert data["JobId"] == "4138646"
        assert data["JobName"] == "bert-20k-preprocess_all"
        assert data["JobState"] == "RUNNING"
        assert data["RunTime"] == "3-03:54:07"
        assert data["TimeLimit"] == "9-04:00:00"
        assert data["NumCPUs"] == "12"
        assert data["Partition"] == "allgroups"
        assert data["NodeList"] == "runner-01"
        assert data["ReqTRES"] == "cpu=12,mem=512G,node=1,billing=12"
        assert data["StdOut"] == "/home/spanio/jobs/tmp/mxlGPT/logs/preprocess_all_4138646.out"
        assert data["StdErr"] == "/home/spanio/jobs/tmp/mxlGPT/logs/preprocess_all_4138646.err"
        assert data["Command"] == "/home/spanio/jobs/tmp/mxlGPT/scripts/unipd_preprocess.sh"

    def test_empty_output(self):
        assert parse_scontrol_output("") == {}

    def test_simple_key_value(self):
        data = parse_scontrol_output("Key1=Value1 Key2=Value2")
        assert data["Key1"] == "Value1"
        assert data["Key2"] == "Value2"


class TestParseTresMem:
    def test_extracts_memory(self):
        assert parse_tres_mem("cpu=12,mem=512G,node=1,billing=12") == "512G"

    def test_memory_in_megabytes(self):
        assert parse_tres_mem("cpu=4,mem=8192M") == "8192M"

    def test_no_memory(self):
        assert parse_tres_mem("cpu=4,node=1") == ""

    def test_empty_string(self):
        assert parse_tres_mem("") == ""


class TestParseMemBytes:
    def test_gigabytes(self):
        assert parse_mem_bytes("512G") == 512 * 1024**3

    def test_megabytes(self):
        assert parse_mem_bytes("1024M") == 1024 * 1024**2

    def test_kilobytes(self):
        assert parse_mem_bytes("300876720K") == 300876720 * 1024

    def test_terabytes(self):
        assert parse_mem_bytes("2T") == 2 * 1024**4

    def test_plain_bytes(self):
        assert parse_mem_bytes("4096") == 4096

    def test_empty_string(self):
        assert parse_mem_bytes("") == 0

    def test_invalid_string(self):
        assert parse_mem_bytes("invalid") == 0


class TestFormatMemHuman:
    def test_zero(self):
        assert format_mem_human(0) == "0"

    def test_gigabytes(self):
        result = format_mem_human(512 * 1024**3)
        assert result == "512G"

    def test_megabytes(self):
        result = format_mem_human(256 * 1024**2)
        assert result == "256M"

    def test_kilobytes(self):
        result = format_mem_human(1024)
        assert result == "1K"


class TestBuildJobDetails:
    def test_from_real_scontrol_data(self):
        data = parse_scontrol_output(SCONTROL_OUTPUT)
        details = build_job_details(data, mem_used_raw="300876720K")

        assert details.run_time == "3-03:54:07"
        assert details.time_limit == "9-04:00:00"
        assert details.time_percentage > 0
        assert details.time_percentage < 100

        assert details.mem_requested == "512G"
        assert details.mem_used != ""
        assert details.mem_percentage > 0
        assert details.mem_percentage < 100

        assert details.num_cpus == 12
        assert details.partition == "allgroups"
        assert details.node_list == "runner-01"
        assert details.stdout_path.endswith(".out")
        assert details.stderr_path.endswith(".err")

    def test_no_memory_used(self):
        data = parse_scontrol_output(SCONTROL_OUTPUT)
        details = build_job_details(data, mem_used_raw="")
        assert details.mem_used == ""
        assert details.mem_percentage == 0.0

    def test_time_percentage_calculation(self):
        data = {"RunTime": "12:00:00", "TimeLimit": "1-00:00:00", "ReqTRES": ""}
        details = build_job_details(data)
        assert details.time_percentage == 50.0

    def test_zero_time_limit(self):
        data = {"RunTime": "01:00:00", "TimeLimit": "UNLIMITED", "ReqTRES": ""}
        details = build_job_details(data)
        assert details.time_percentage == 0.0


class TestFetchJobDetails:
    def test_success(self):
        config = SSHConfig(host="testhost")
        client = SSHClient(config)

        with patch.object(client, "execute") as mock_exec:
            mock_exec.side_effect = [
                SCONTROL_OUTPUT,  # scontrol
                "300876720K",  # sstat
            ]
            details = fetch_job_details(client, "4138646")

        assert details is not None
        assert details.num_cpus == 12
        assert details.mem_used != ""

    def test_scontrol_failure_returns_none(self):
        config = SSHConfig(host="testhost")
        client = SSHClient(config)

        with patch.object(
            client, "execute", side_effect=SSHConnectionError("fail")
        ):
            details = fetch_job_details(client, "4138646")

        assert details is None

    def test_sstat_failure_still_returns_details(self):
        config = SSHConfig(host="testhost")
        client = SSHClient(config)

        with patch.object(client, "execute") as mock_exec:
            mock_exec.side_effect = [
                SCONTROL_OUTPUT,  # scontrol succeeds
                SSHConnectionError("sstat fail"),  # sstat fails
            ]
            details = fetch_job_details(client, "4138646")

        assert details is not None
        assert details.mem_used == ""
        assert details.num_cpus == 12

    def test_completed_job_skips_sstat(self):
        completed_output = SCONTROL_OUTPUT.replace("JobState=RUNNING", "JobState=COMPLETED")
        config = SSHConfig(host="testhost")
        client = SSHClient(config)

        with patch.object(client, "execute") as mock_exec:
            mock_exec.return_value = completed_output
            details = fetch_job_details(client, "4138646")

        # Only scontrol called, not sstat
        mock_exec.assert_called_once()
        assert details is not None
        assert details.mem_used == ""
