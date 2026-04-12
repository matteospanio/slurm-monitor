"""Parser for Slurm sacct command output."""

from typing import Optional

from slurm_monitor.ssh_wrapper import SSHClient
from slurm_monitor.squeue_parser import SlurmJob


def parse_sacct_line(line: str) -> Optional[SlurmJob]:
    """Parse a single line of sacct output.

    Sacct uses whitespace-separated columns with potential spaces in values.
    Format: JobID JobName State Elapsed WorkDir

    Args:
        line: A whitespace-formatted line from sacct output

    Returns:
        SlurmJob object with parsed data, or None if line is invalid
    """
    line = line.strip()
    if not line:
        return None

    parts = line.split(None, 4)

    if len(parts) < 4:
        return None

    job_id = parts[0]
    name = parts[1]
    state = parts[2]
    time = parts[3]
    work_dir = parts[4] if len(parts) > 4 else None

    return SlurmJob(
        job_id=job_id,
        name=name,
        state=state,
        time=time,
        work_dir=work_dir,
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
    format_fields: str = "JobID,JobName,State,Elapsed,WorkDir",
) -> list[SlurmJob]:
    """Fetch and parse historical jobs from sacct on a remote host.

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
    command = f"sacct -X --format={format_fields} --units=M -n"
    output = client.execute(command, timeout)
    return parse_sacct_output(output)


def jobs_to_dict_list(jobs: list[SlurmJob]) -> list[dict[str, Optional[str]]]:
    """Convert a list of SlurmJob objects to a list of dictionaries."""
    return [job.to_dict() for job in jobs]
