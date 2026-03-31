"""Data aggregation service for merging active and historical Slurm jobs."""

from typing import Optional

from slurm_monitor.sacct_parser import fetch_sacct_jobs
from slurm_monitor.squeue_parser import SlurmJob, fetch_squeue_jobs


class JobAggregator:
    """Service for aggregating job data from multiple sources."""

    def __init__(self, host: str, timeout: int = 10):
        """
        Initialize the job aggregator.

        Args:
            host: Remote Slurm cluster host
            timeout: SSH command timeout in seconds
        """
        self.host = host
        self.timeout = timeout

    def fetch_all_jobs(self) -> list[SlurmJob]:
        """
        Fetch and merge jobs from both squeue (active) and sacct (history).

        Active jobs from squeue take precedence over historical data from sacct
        if there are duplicate job IDs.

        Returns:
            Unified list of SlurmJob objects sorted by job ID (descending)

        Raises:
            SSHConnectionError: If SSH connection fails
            SSHTimeoutError: If command times out
        """
        # Fetch active jobs from squeue
        active_jobs = fetch_squeue_jobs(self.host, timeout=self.timeout)

        # Fetch historical jobs from sacct
        historical_jobs = fetch_sacct_jobs(self.host, timeout=self.timeout)

        # Merge jobs with active jobs taking precedence
        merged_jobs = merge_jobs(active_jobs, historical_jobs)

        return merged_jobs


def merge_jobs(
    active_jobs: list[SlurmJob],
    historical_jobs: list[SlurmJob],
) -> list[SlurmJob]:
    """
    Merge active and historical job lists.

    Active jobs take precedence over historical jobs if duplicates exist.
    Result is sorted by job ID in descending order (newest first).

    Args:
        active_jobs: List of jobs from squeue (active)
        historical_jobs: List of jobs from sacct (history)

    Returns:
        Merged and sorted list of unique jobs
    """
    # Use a dictionary to handle deduplication
    # Key: job_id, Value: SlurmJob
    job_dict: dict[str, SlurmJob] = {}

    # Add historical jobs first
    for job in historical_jobs:
        job_dict[job.job_id] = job

    # Add active jobs, overwriting any duplicates from history
    for job in active_jobs:
        job_dict[job.job_id] = job

    # Convert back to list and sort by job_id (descending)
    # Job IDs are typically numeric, so convert for proper sorting
    merged_list = list(job_dict.values())
    merged_list.sort(key=lambda job: int(job.job_id), reverse=True)

    return merged_list


def _time_to_seconds(time_str: str) -> int:
    """
    Convert a Slurm time string to total seconds for comparison.

    Supports formats: MM:SS, HH:MM:SS, D-HH:MM:SS

    Args:
        time_str: Time string from Slurm output

    Returns:
        Total seconds, or 0 if parsing fails
    """
    try:
        days = 0
        if "-" in time_str:
            day_part, time_str = time_str.split("-", 1)
            days = int(day_part)

        parts = time_str.split(":")
        if len(parts) == 3:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        elif len(parts) == 2:
            hours = 0
            minutes, seconds = int(parts[0]), int(parts[1])
        else:
            return 0

        return days * 86400 + hours * 3600 + minutes * 60 + seconds
    except (ValueError, IndexError):
        return 0


def sort_jobs_by_time(jobs: list[SlurmJob], reverse: bool = True) -> list[SlurmJob]:
    """
    Sort jobs by elapsed time.

    Args:
        jobs: List of SlurmJob objects
        reverse: If True, sort descending (longest time first)

    Returns:
        Sorted list of jobs

    Note:
        Time formats supported: MM:SS, HH:MM:SS, D-HH:MM:SS
    """
    return sorted(jobs, key=lambda job: _time_to_seconds(job.time), reverse=reverse)


def filter_jobs_by_state(
    jobs: list[SlurmJob],
    states: list[str],
) -> list[SlurmJob]:
    """
    Filter jobs by their state.

    Args:
        jobs: List of SlurmJob objects
        states: List of states to include (e.g., ["RUNNING", "PENDING"])

    Returns:
        Filtered list of jobs
    """
    return [job for job in jobs if job.state in states]


def get_job_by_id(jobs: list[SlurmJob], job_id: str) -> Optional[SlurmJob]:
    """
    Find a job by its ID.

    Args:
        jobs: List of SlurmJob objects
        job_id: Job ID to search for

    Returns:
        SlurmJob if found, None otherwise
    """
    for job in jobs:
        if job.job_id == job_id:
            return job
    return None


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python -m slurm_monitor.job_aggregator <host>")
        sys.exit(1)

    host = sys.argv[1]

    try:
        aggregator = JobAggregator(host)
        jobs = aggregator.fetch_all_jobs()

        # Convert to dict for JSON output
        jobs_data = [job.to_dict() for job in jobs]
        print(json.dumps(jobs_data, indent=2))
        print(f"\nTotal jobs: {len(jobs)}", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
