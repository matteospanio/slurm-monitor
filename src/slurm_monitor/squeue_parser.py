"""Parser for Slurm squeue command output."""

from dataclasses import dataclass
from typing import Optional

from slurm_monitor.ssh_wrapper import execute_ssh_command


@dataclass
class SlurmJob:
    """Represents a Slurm job with its metadata."""

    job_id: str
    name: str
    state: str
    time: str
    work_dir: Optional[str] = None

    def to_dict(self) -> dict[str, Optional[str]]:
        """Convert job to dictionary representation."""
        return {
            "job_id": self.job_id,
            "name": self.name,
            "state": self.state,
            "time": self.time,
            "work_dir": self.work_dir,
        }


def parse_squeue_line(line: str) -> SlurmJob:
    """
    Parse a single line of squeue output.

    Args:
        line: A pipe-delimited line from squeue output
              Format: JobID|JobName|State|Time|WorkDir

    Returns:
        SlurmJob object with parsed data

    Raises:
        ValueError: If line format is invalid
    """
    parts = line.strip().split("|")

    if len(parts) < 4:
        raise ValueError(
            f"Invalid squeue line format. Expected at least 4 fields, got {len(parts)}: {line}"
        )

    # Handle optional WorkDir field (5th column)
    work_dir = parts[4] if len(parts) > 4 and parts[4] else None

    return SlurmJob(
        job_id=parts[0],
        name=parts[1],
        state=parts[2],
        time=parts[3],
        work_dir=work_dir,
    )


def parse_squeue_output(output: str) -> list[SlurmJob]:
    """
    Parse complete squeue output into a list of jobs.

    Args:
        output: Raw stdout from squeue command

    Returns:
        List of SlurmJob objects
    """
    if not output.strip():
        return []

    jobs = []
    for line in output.strip().split("\n"):
        if line.strip():
            try:
                job = parse_squeue_line(line)
                jobs.append(job)
            except ValueError:
                # Skip malformed lines but continue parsing
                continue

    return jobs


def fetch_squeue_jobs(
    host: str,
    timeout: int = 10,
    format_string: str = "%i|%j|%T|%M|%Z",
) -> list[SlurmJob]:
    """
    Fetch and parse jobs from squeue on a remote host.

    Args:
        host: Remote Slurm cluster host
        timeout: SSH command timeout in seconds
        format_string: squeue output format string
                      Default: %i (JobID) | %j (Name) | %T (State) |
                               %M (Time) | %Z (WorkDir)

    Returns:
        List of SlurmJob objects

    Raises:
        SSHConnectionError: If SSH connection fails
        SSHTimeoutError: If command times out
    """
    command = f'squeue --me -o "{format_string}" --noheader'
    output = execute_ssh_command(host, command, timeout)
    return parse_squeue_output(output)


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
        print("Usage: python -m slurm_monitor.squeue_parser <host>")
        sys.exit(1)

    host = sys.argv[1]

    try:
        jobs = fetch_squeue_jobs(host)
        jobs_data = jobs_to_dict_list(jobs)
        print(json.dumps(jobs_data, indent=2))
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
