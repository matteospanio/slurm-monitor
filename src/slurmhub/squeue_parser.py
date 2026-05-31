"""Parser for Slurm squeue command output."""

from dataclasses import dataclass
from typing import Optional

from slurmhub.ssh_wrapper import SSHClient


@dataclass
class SlurmJob:
    """Represents a Slurm job with its metadata."""

    job_id: str
    name: str
    state: str
    time: str
    work_dir: Optional[str] = None
    gres: Optional[str] = None
    # Pending job fields (populated for PENDING jobs only)
    pending_reason: Optional[str] = None
    priority: Optional[int] = None
    qos: Optional[str] = None
    submit_time: Optional[str] = None
    queue_rank: Optional[int] = None
    # Allocated/requested resources (captured for job history).
    num_cpus: Optional[int] = None
    mem_requested_mb: Optional[int] = None

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


def _to_int(value: str) -> Optional[int]:
    """Parse an integer field, returning None for blanks/``N/A``."""
    value = value.strip()
    if not value or value in ("N/A", "(null)"):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def mem_str_to_mb(value: Optional[str]) -> Optional[int]:
    """Convert a Slurm memory string to whole megabytes, or None.

    Handles a unit suffix (K/M/G/T), bare integers (already MB — as emitted by
    ``squeue %m`` and ``sacct --units=M``), and a trailing per-node/per-cpu
    marker (e.g. ``16Gn``, ``4Gc``).
    """
    if not value:
        return None
    value = value.strip()
    if not value or value in ("N/A", "(null)", "0"):
        return None if value in ("N/A", "(null)") else 0
    if value[-1] in ("c", "n"):  # per-cpu / per-node marker
        value = value[:-1]
    if not value:
        return None
    suffix = value[-1].upper()
    factors_to_mb = {"K": 1 / 1024, "M": 1.0, "G": 1024.0, "T": 1024.0 * 1024.0}
    try:
        if suffix in factors_to_mb:
            return int(float(value[:-1]) * factors_to_mb[suffix])
        return int(float(value))  # bare value is already MB
    except ValueError:
        return None


def parse_squeue_line(line: str) -> SlurmJob:
    """Parse a single line of squeue output.

    Args:
        line: A pipe-delimited line from squeue output. Format:
              ``JobID|JobName|State|Time|WorkDir|Gres[|SubmitTime|CPUs|Mem]``

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
    submit_time = (
        parts[6] if len(parts) > 6 and parts[6] not in ("", "N/A") else None
    )
    num_cpus = _to_int(parts[7]) if len(parts) > 7 else None
    mem_requested_mb = mem_str_to_mb(parts[8]) if len(parts) > 8 else None

    return SlurmJob(
        job_id=parts[0],
        name=parts[1],
        state=parts[2],
        time=parts[3],
        work_dir=work_dir,
        gres=gres,
        submit_time=submit_time,
        num_cpus=num_cpus,
        mem_requested_mb=mem_requested_mb,
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
    format_string: str = "%i|%j|%T|%M|%Z|%b|%V|%C|%m",
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
