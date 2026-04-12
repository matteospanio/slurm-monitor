"""Parser for Slurm squeue command output."""

from dataclasses import dataclass
from typing import Optional

from slurm_monitor.ssh_wrapper import SSHClient


@dataclass
class SlurmJob:
    """Represents a Slurm job with its metadata."""

    job_id: str
    name: str
    state: str
    time: str
    work_dir: Optional[str] = None
    gres: Optional[str] = None

    def to_dict(self) -> dict[str, Optional[str]]:
        """Convert job to dictionary representation."""
        return {
            "job_id": self.job_id,
            "name": self.name,
            "state": self.state,
            "time": self.time,
            "work_dir": self.work_dir,
            "gres": self.gres,
        }

    @property
    def gpu_display(self) -> str:
        """Return a human-readable GPU string like '4x l40s' or ''."""
        if not self.gres or self.gres == "(null)":
            return ""
        # gres format: gpu:type:count or gpu:count
        for part in self.gres.split(","):
            part = part.strip()
            if part.startswith("gpu:"):
                segments = part.split(":")
                if len(segments) == 3:
                    # gpu:type:count
                    return f"{segments[2]}x {segments[1]}"
                elif len(segments) == 2:
                    # gpu:count
                    return f"{segments[1]}x gpu"
        return ""


def parse_squeue_line(line: str) -> SlurmJob:
    """Parse a single line of squeue output.

    Args:
        line: A pipe-delimited line from squeue output
              Format: JobID|JobName|State|Time|WorkDir|Gres

    Returns:
        SlurmJob object with parsed data

    Raises:
        ValueError: If line format is invalid
    """
    parts = line.strip().split("|")

    if len(parts) < 4:
        raise ValueError(
            f"Invalid squeue line format. Expected at least 4 fields, "
            f"got {len(parts)}: {line}"
        )

    work_dir = parts[4] if len(parts) > 4 and parts[4] else None
    gres = parts[5] if len(parts) > 5 and parts[5] else None

    return SlurmJob(
        job_id=parts[0],
        name=parts[1],
        state=parts[2],
        time=parts[3],
        work_dir=work_dir,
        gres=gres,
    )


def parse_squeue_output(output: str) -> list[SlurmJob]:
    """Parse complete squeue output into a list of jobs.

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
                continue

    return jobs


def fetch_squeue_jobs(
    client: SSHClient,
    timeout: int = 10,
    format_string: str = "%i|%j|%T|%M|%Z|%b",
) -> list[SlurmJob]:
    """Fetch and parse jobs from squeue on a remote host.

    Args:
        client: SSHClient connected to the Slurm cluster
        timeout: SSH command timeout in seconds
        format_string: squeue output format string

    Returns:
        List of SlurmJob objects

    Raises:
        SSHConnectionError: If SSH connection fails
        SSHTimeoutError: If command times out
    """
    command = f'squeue --me -o "{format_string}" --noheader'
    output = client.execute(command, timeout)
    return parse_squeue_output(output)


def jobs_to_dict_list(jobs: list[SlurmJob]) -> list[dict[str, Optional[str]]]:
    """Convert a list of SlurmJob objects to a list of dictionaries."""
    return [job.to_dict() for job in jobs]
