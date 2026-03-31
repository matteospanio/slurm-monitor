"""Parser for Slurm sacct command output."""

from typing import Optional

from slurm_monitor.ssh_wrapper import execute_ssh_command
from slurm_monitor.squeue_parser import SlurmJob


def parse_sacct_line(line: str) -> Optional[SlurmJob]:
    """
    Parse a single line of sacct output.

    Sacct uses whitespace-separated columns with potential spaces in values.
    Format: JobID JobName State Elapsed WorkDir

    Args:
        line: A whitespace-formatted line from sacct output

    Returns:
        SlurmJob object with parsed data, or None if line is invalid

    Note:
        Sacct output is whitespace-delimited, which is more challenging to parse
        than pipe-delimited output. We use a regex approach to handle this.
    """
    line = line.strip()
    if not line:
        return None

    # Sacct format: JobID (whitespace) JobName (whitespace) State (whitespace) Elapsed (whitespace) WorkDir
    # We need to split on whitespace but handle cases where fields might contain spaces
    # For robust parsing, we expect at least 5 columns
    parts = line.split(None, 4)  # Split on any whitespace, max 5 parts

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
    """
    Parse complete sacct output into a list of jobs.

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
    host: str,
    timeout: int = 10,
    format_fields: str = "JobID,JobName,State,Elapsed,WorkDir",
) -> list[SlurmJob]:
    """
    Fetch and parse historical jobs from sacct on a remote host.

    Args:
        host: Remote Slurm cluster host
        timeout: SSH command timeout in seconds
        format_fields: Comma-separated list of sacct fields to display
                      Default: JobID,JobName,State,Elapsed,WorkDir

    Returns:
        List of SlurmJob objects

    Raises:
        SSHConnectionError: If SSH connection fails
        SSHTimeoutError: If command times out
    """
    command = f"sacct -X --format={format_fields} --units=M -n"
    output = execute_ssh_command(host, command, timeout)
    return parse_sacct_output(output)


def jobs_to_dict_list(jobs: list[SlurmJob]) -> list[dict[str, Optional[str]]]:
    """
    Convert a list of SlurmJob objects to a list of dictionaries.

    Args:
        jobs: List of SlurmJob objects

    Returns:
        List of dictionaries representing jobs
    """
    return [job.to_dict() for job in jobs]


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python -m slurm_monitor.sacct_parser <host>")
        sys.exit(1)

    host = sys.argv[1]

    try:
        jobs = fetch_sacct_jobs(host)
        jobs_data = jobs_to_dict_list(jobs)
        print(json.dumps(jobs_data, indent=2))
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
