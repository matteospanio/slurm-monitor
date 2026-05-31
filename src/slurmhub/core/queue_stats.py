"""Cluster-wide queue statistics and pending job details."""

from dataclasses import dataclass
from typing import Optional

from slurmhub.slurm.ssh import SSHClient


@dataclass
class ClusterQueueStats:
    """Cluster-wide job queue summary."""

    total_running: int = 0
    total_pending: int = 0
    total_other: int = 0
    fetched_at: Optional[str] = None


@dataclass
class PendingInfo:
    """Pending job details from squeue."""

    reason: str
    priority: int
    submit_time: str
    qos: str


def parse_cluster_queue_stats(output: str) -> ClusterQueueStats:
    """Parse output of ``squeue --noheader -o "%T"`` into counts by state.

    Args:
        output: Raw stdout, one state string per line.

    Returns:
        ClusterQueueStats with counts.
    """
    running = 0
    pending = 0
    other = 0

    for line in output.strip().splitlines():
        state = line.strip()
        if not state:
            continue
        if state == "RUNNING":
            running += 1
        elif state == "PENDING":
            pending += 1
        else:
            other += 1

    return ClusterQueueStats(
        total_running=running,
        total_pending=pending,
        total_other=other,
    )


def fetch_cluster_queue_stats(
    client: SSHClient, timeout: int = 10
) -> ClusterQueueStats:
    """Fetch cluster-wide queue state counts.

    Runs ``squeue --noheader -o "%T"`` to get one state per line for all jobs.
    """
    from datetime import datetime

    output = client.execute('squeue --noheader -o "%T"', timeout)
    stats = parse_cluster_queue_stats(output)
    stats.fetched_at = datetime.now().strftime("%H:%M:%S")
    return stats


def parse_pending_details(output: str) -> dict[str, PendingInfo]:
    """Parse output of ``squeue --me -t PENDING --noheader -o "%i|%r|%Q|%V|%q"``.

    Args:
        output: Pipe-delimited lines with JobID|Reason|Priority|SubmitTime|QOS.

    Returns:
        Dict mapping job_id to PendingInfo.
    """
    result: dict[str, PendingInfo] = {}

    for line in output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) < 5:
            continue
        try:
            result[parts[0]] = PendingInfo(
                reason=parts[1],
                priority=int(parts[2]),
                submit_time=parts[3],
                qos=parts[4],
            )
        except (ValueError, IndexError):
            continue

    return result


def fetch_pending_details(
    client: SSHClient, timeout: int = 10
) -> dict[str, PendingInfo]:
    """Fetch pending details for the current user's pending jobs."""
    output = client.execute(
        'squeue --me -t PENDING --noheader -o "%i|%r|%Q|%V|%q"', timeout
    )
    return parse_pending_details(output)


def parse_queue_ranks(output: str) -> list[str]:
    """Parse output of ``squeue -t PENDING --noheader -o "%Q|%i" --sort=-Q``.

    Returns list of job_ids in priority order (highest first).
    """
    job_ids: list[str] = []
    for line in output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 2:
            job_ids.append(parts[1].strip())
    return job_ids


def compute_queue_ranks(
    client: SSHClient, user_job_ids: list[str], timeout: int = 10
) -> dict[str, int]:
    """Compute 1-based queue rank for the given user job IDs.

    Runs ``squeue -t PENDING --noheader -o "%Q|%i" --sort=-Q`` to get all
    pending jobs sorted by priority (descending), then finds where the
    user's jobs fall in that list.

    Returns:
        Dict mapping job_id to 1-based rank in the pending queue.
    """
    if not user_job_ids:
        return {}

    output = client.execute(
        'squeue -t PENDING --noheader -o "%Q|%i" --sort=-Q', timeout
    )
    all_pending = parse_queue_ranks(output)

    user_set = set(user_job_ids)
    ranks: dict[str, int] = {}
    for rank, job_id in enumerate(all_pending, start=1):
        if job_id in user_set:
            ranks[job_id] = rank

    return ranks
