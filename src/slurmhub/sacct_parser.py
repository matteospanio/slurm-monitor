"""Parser for Slurm sacct command output."""

from typing import Optional

from slurmhub.squeue_parser import SlurmJob, _to_int, mem_str_to_mb
from slurmhub.ssh_wrapper import SSHClient


def parse_sacct_line(line: str) -> Optional[SlurmJob]:
    """Parse a single line of pipe-delimited (``--parsable2``) sacct output.

    Format: ``JobID|JobName|State|Elapsed|Submit|NCPUS|ReqMem|WorkDir``.
    Pipe delimiting is robust to spaces in job names, work dirs, and state
    strings (e.g. ``CANCELLED by 1001``).

    Args:
        line: A pipe-delimited line from sacct output

    Returns:
        SlurmJob object with parsed data, or None if line is invalid
    """
    line = line.strip()
    if not line:
        return None

    parts = line.split("|")

    if len(parts) < 4:
        return None

    job_id = parts[0]
    name = parts[1]
    state = parts[2]
    time = parts[3]
    submit_time = (
        parts[4] if len(parts) > 4 and parts[4] not in ("", "N/A") else None
    )
    num_cpus = _to_int(parts[5]) if len(parts) > 5 else None
    mem_requested_mb = mem_str_to_mb(parts[6]) if len(parts) > 6 else None
    work_dir = parts[7] if len(parts) > 7 and parts[7] else None

    return SlurmJob(
        job_id=job_id,
        name=name,
        state=state,
        time=time,
        work_dir=work_dir,
        submit_time=submit_time,
        num_cpus=num_cpus,
        mem_requested_mb=mem_requested_mb,
    )


def parse_sacct_output(output: str) -> list[SlurmJob]:
    """Parse complete sacct output into a list of jobs.

    Args:
        output: Raw stdout from sacct command

    Returns:
        List of SlurmJob objects
    """
    if not output.strip():
        return []

    jobs = []
    for line in output.strip().split("\n"):
        job = parse_sacct_line(line)
        if job:
            jobs.append(job)

    return jobs


def fetch_sacct_jobs(
    client: SSHClient,
    timeout: int = 10,
    format_fields: str = "JobID,JobName,State,Elapsed,Submit,NCPUS,ReqMem,WorkDir",
) -> list[SlurmJob]:
    """Fetch and parse historical jobs from sacct on a remote host.

    Uses ``--parsable2`` so columns are pipe-delimited (robust to spaces) and
    ``--units=M`` so ReqMem is reported in megabytes.

    Args:
        client: SSHClient connected to the Slurm cluster
        timeout: SSH command timeout in seconds
        format_fields: Comma-separated list of sacct fields to display

    Returns:
        List of SlurmJob objects

    Raises:
        SSHConnectionError: If SSH connection fails
        SSHTimeoutError: If command times out
    """
    command = f"sacct -X --format={format_fields} --units=M -n -P"
    output = client.execute(command, timeout)
    return parse_sacct_output(output)


def jobs_to_dict_list(jobs: list[SlurmJob]) -> list[dict[str, Optional[str]]]:
    """Convert a list of SlurmJob objects to a list of dictionaries."""
    return [job.to_dict() for job in jobs]
