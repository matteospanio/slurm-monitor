"""Parser for Slurm scontrol show job output and sstat memory data."""

import re
from dataclasses import dataclass
from typing import Optional

from slurm_monitor.job_aggregator import time_to_seconds
from slurm_monitor.ssh_wrapper import SSHClient


@dataclass
class JobDetails:
    """Extended job details from scontrol and sstat."""

    time_limit: str = ""
    run_time: str = ""
    time_percentage: float = 0.0
    mem_requested: str = ""
    mem_used: str = ""
    mem_percentage: float = 0.0
    num_cpus: int = 0
    partition: str = ""
    node_list: str = ""
    submit_time: str = ""
    start_time: str = ""
    end_time: str = ""
    command: str = ""
    stdout_path: str = ""
    stderr_path: str = ""


def parse_scontrol_output(output: str) -> dict[str, str]:
    """Parse scontrol show job output into a key-value dict.

    scontrol output has the form:
        Key1=Value1 Key2=Value2
        Key3=Value3
    Values may contain spaces when they span a path, but keys never do.

    Args:
        output: Raw stdout from 'scontrol show job <id>'

    Returns:
        Dictionary of key-value pairs
    """
    result: dict[str, str] = {}
    # Collapse all whitespace-separated lines into one string
    flat = " ".join(output.split())
    # Split on key=value boundaries: a space followed by a key and '='
    # Keys may contain word chars, colons, or slashes (e.g. AllocNode:Sid, CPUs/Task)
    tokens = re.split(r"\s+(?=[\w:/]+=)", flat)
    for token in tokens:
        if "=" in token:
            key, _, value = token.partition("=")
            result[key.strip()] = value.strip()
    return result


def parse_tres_mem(tres_str: str) -> str:
    """Extract memory value from a TRES string like 'cpu=12,mem=512G,node=1'.

    Returns the raw memory string (e.g. '512G') or '' if not found.
    """
    for part in tres_str.split(","):
        if part.startswith("mem="):
            return part[4:]
    return ""


def parse_mem_bytes(mem_str: str) -> int:
    """Parse a memory string with unit suffix to bytes.

    Supports K, M, G, T suffixes (case-insensitive).
    Also handles plain integers (assumed bytes).

    Args:
        mem_str: Memory string like '512G', '300876720K', '1024M'

    Returns:
        Size in bytes, or 0 if parsing fails
    """
    if not mem_str:
        return 0
    mem_str = mem_str.strip()
    multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    suffix = mem_str[-1].upper()
    if suffix in multipliers:
        try:
            return int(float(mem_str[:-1]) * multipliers[suffix])
        except ValueError:
            return 0
    try:
        return int(mem_str)
    except ValueError:
        return 0


def format_mem_human(mem_bytes: int) -> str:
    """Format bytes into a human-readable string.

    Args:
        mem_bytes: Size in bytes

    Returns:
        Human-readable string like '512.0G', '4.2M'
    """
    if mem_bytes == 0:
        return "0"
    value = float(mem_bytes)
    for unit in ["", "K", "M", "G", "T"]:
        if abs(value) < 1024:
            if value == int(value):
                return f"{int(value)}{unit}"
            return f"{value:.1f}{unit}"
        value /= 1024
    if value == int(value):
        return f"{int(value)}P"
    return f"{value:.1f}P"


def build_job_details(scontrol_data: dict[str, str], mem_used_raw: str = "") -> JobDetails:
    """Build a JobDetails from parsed scontrol data and optional sstat memory.

    Args:
        scontrol_data: Dict from parse_scontrol_output
        mem_used_raw: Raw MaxRSS string from sstat (e.g. '300876720K')

    Returns:
        Populated JobDetails
    """
    run_time = scontrol_data.get("RunTime", "")
    time_limit = scontrol_data.get("TimeLimit", "")

    # Time percentage
    run_seconds = time_to_seconds(run_time)
    limit_seconds = time_to_seconds(time_limit)
    time_pct = (run_seconds / limit_seconds * 100) if limit_seconds > 0 else 0.0

    # Memory requested from TRES
    req_tres = scontrol_data.get("ReqTRES", "")
    mem_req_str = parse_tres_mem(req_tres)
    mem_req_bytes = parse_mem_bytes(mem_req_str)

    # Memory used from sstat
    mem_used_bytes = parse_mem_bytes(mem_used_raw)
    mem_pct = (mem_used_bytes / mem_req_bytes * 100) if mem_req_bytes > 0 else 0.0

    return JobDetails(
        time_limit=time_limit,
        run_time=run_time,
        time_percentage=round(time_pct, 1),
        mem_requested=mem_req_str or format_mem_human(mem_req_bytes),
        mem_used=format_mem_human(mem_used_bytes) if mem_used_bytes else "",
        mem_percentage=round(mem_pct, 1),
        num_cpus=int(scontrol_data.get("NumCPUs", "0") or "0"),
        partition=scontrol_data.get("Partition", ""),
        node_list=scontrol_data.get("NodeList", ""),
        submit_time=scontrol_data.get("SubmitTime", ""),
        start_time=scontrol_data.get("StartTime", ""),
        end_time=scontrol_data.get("EndTime", ""),
        command=scontrol_data.get("Command", ""),
        stdout_path=scontrol_data.get("StdOut", ""),
        stderr_path=scontrol_data.get("StdErr", ""),
    )


def fetch_job_details(
    client: SSHClient, job_id: str, timeout: int = 10
) -> Optional[JobDetails]:
    """Fetch extended job details via scontrol and sstat.

    Args:
        client: Connected SSHClient
        job_id: Slurm job ID
        timeout: SSH command timeout

    Returns:
        JobDetails or None if scontrol fails
    """
    try:
        output = client.execute(f"scontrol show job {job_id}", timeout)
    except Exception:
        return None

    scontrol_data = parse_scontrol_output(output)
    if not scontrol_data:
        return None

    # Try to get actual memory usage for running jobs
    mem_used_raw = ""
    state = scontrol_data.get("JobState", "")
    if state == "RUNNING":
        try:
            sstat_out = client.execute(
                f"sstat --format=MaxRSS -j {job_id}.batch --noheader 2>/dev/null",
                timeout,
            )
            mem_used_raw = sstat_out.strip()
        except Exception:
            pass

    return build_job_details(scontrol_data, mem_used_raw)
