"""Parser for Slurm scontrol show job output, sstat, and GPU data."""

import re
from dataclasses import dataclass, field
from typing import Optional

from slurmhub.slurm.ssh import SSHClient
from slurmhub.slurm.util import time_to_seconds


@dataclass
class GpuInfo:
    """Usage info for a single GPU."""

    index: int = 0
    name: str = ""
    utilization: int = 0  # percentage 0-100
    mem_used_mb: int = 0
    mem_total_mb: int = 0

    @property
    def mem_percentage(self) -> float:
        if self.mem_total_mb > 0:
            return round(self.mem_used_mb / self.mem_total_mb * 100, 1)
        return 0.0


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
    num_gpus: int = 0
    gpu_type: str = ""
    gpus: list[GpuInfo] = field(default_factory=list)
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


def parse_tres_gpu(tres_str: str) -> tuple[int, str]:
    """Extract GPU count and type from a TRES string.

    Examples:
        'cpu=20,mem=100G,gres/gpu=4,gres/gpu:l40s=4' -> (4, 'l40s')
        'cpu=12,mem=512G' -> (0, '')

    Returns:
        Tuple of (gpu_count, gpu_type)
    """
    gpu_count = 0
    gpu_type = ""
    for part in tres_str.split(","):
        # Match gres/gpu:type=N (specific type)
        m = re.match(r"gres/gpu:(\w+)=(\d+)", part)
        if m:
            gpu_type = m.group(1)
            gpu_count = int(m.group(2))
            continue
        # Match gres/gpu=N (generic count, only if no typed match yet)
        m = re.match(r"gres/gpu=(\d+)", part)
        if m and gpu_count == 0:
            gpu_count = int(m.group(1))
    return gpu_count, gpu_type


def parse_nvidia_smi_output(output: str) -> list[GpuInfo]:
    """Parse nvidia-smi CSV output into GpuInfo list.

    Expected format (per line):
        index, name, utilization.gpu, memory.used, memory.total

    Args:
        output: Raw nvidia-smi --format=csv,noheader,nounits output

    Returns:
        List of GpuInfo objects
    """
    gpus = []
    for line in output.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        try:
            gpus.append(GpuInfo(
                index=int(parts[0]),
                name=parts[1],
                utilization=int(parts[2]),
                mem_used_mb=int(parts[3]),
                mem_total_mb=int(parts[4]),
            ))
        except (ValueError, IndexError):
            continue
    return gpus


def build_job_details(scontrol_data: dict[str, str], mem_used_raw: str = "", gpus: Optional[list[GpuInfo]] = None) -> JobDetails:
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

    # GPU info from TRES
    gpu_count, gpu_type = parse_tres_gpu(req_tres)

    return JobDetails(
        time_limit=time_limit,
        run_time=run_time,
        time_percentage=round(time_pct, 1),
        mem_requested=mem_req_str or format_mem_human(mem_req_bytes),
        mem_used=format_mem_human(mem_used_bytes) if mem_used_bytes else "",
        mem_percentage=round(mem_pct, 1),
        num_cpus=int(scontrol_data.get("NumCPUs", "0") or "0"),
        num_gpus=gpu_count,
        gpu_type=gpu_type,
        gpus=gpus or [],
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

    # For running jobs, fetch live stats
    mem_used_raw = ""
    gpu_list: list[GpuInfo] = []
    state = scontrol_data.get("JobState", "")
    if state == "RUNNING":
        # Memory usage via sstat
        try:
            sstat_out = client.execute(
                f"sstat --format=MaxRSS -j {job_id}.batch --noheader 2>/dev/null",
                timeout,
            )
            mem_used_raw = sstat_out.strip()
        except Exception:
            pass

        # GPU utilization via nvidia-smi (only if job uses GPUs)
        req_tres = scontrol_data.get("ReqTRES", "")
        gpu_count, _ = parse_tres_gpu(req_tres)
        if gpu_count > 0:
            try:
                nvidia_out = client.execute(
                    f"srun --jobid={job_id} --overlap "
                    "nvidia-smi --query-gpu=index,name,utilization.gpu,"
                    "memory.used,memory.total "
                    "--format=csv,noheader,nounits 2>/dev/null",
                    timeout,
                )
                gpu_list = parse_nvidia_smi_output(nvidia_out)
            except Exception:
                pass

    return build_job_details(scontrol_data, mem_used_raw, gpu_list)
