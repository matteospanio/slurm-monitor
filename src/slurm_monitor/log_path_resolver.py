"""Log path resolution strategy for Slurm jobs."""

from pathlib import Path
from typing import Optional

from slurm_monitor.config import Config, LogPathConfig


class LogPathResolver:
    """
    Resolves log file paths based on configuration patterns.

    Supports token replacement and project-specific patterns.
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the path resolver.

        Args:
            config: Configuration object. If None, uses default config.
        """
        if config is None:
            from slurm_monitor.config import ConfigLoader

            config = ConfigLoader.load()

        self.config = config

    def resolve_path(
        self,
        job_id: str,
        work_dir: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> str:
        """
        Resolve the log file path for a job.

        Resolution strategy:
        1. Check if work_dir matches a specific project pattern
        2. If not, use the default pattern
        3. Replace tokens: {job_id}, {work_dir}, {project_name}

        Args:
            job_id: The Slurm job ID
            work_dir: The job's working directory
            project_name: Optional project name for specific patterns

        Returns:
            Resolved log file path as string
        """
        # Determine which pattern to use
        pattern = self._get_pattern(work_dir, project_name)

        # Replace tokens
        resolved = pattern
        resolved = resolved.replace("{job_id}", job_id)

        if work_dir:
            resolved = resolved.replace("{work_dir}", work_dir)

        if project_name:
            resolved = resolved.replace("{project_name}", project_name)

        return resolved

    def _get_pattern(
        self,
        work_dir: Optional[str],
        project_name: Optional[str],
    ) -> str:
        """
        Get the appropriate pattern based on work_dir or project_name.

        Args:
            work_dir: The job's working directory
            project_name: Optional project name

        Returns:
            Pattern string to use for path resolution
        """
        log_paths = self.config.log_paths

        # First priority: explicit project_name
        if project_name and project_name in log_paths.specific_projects:
            return log_paths.specific_projects[project_name]

        # Second priority: check if work_dir matches a project
        if work_dir:
            for project, pattern in log_paths.specific_projects.items():
                # Check if project name appears in work_dir
                if project in work_dir:
                    return pattern

        # Default pattern
        return log_paths.default_pattern

    def resolve_paths_for_jobs(self, jobs: list) -> dict[str, str]:
        """
        Resolve log paths for multiple jobs.

        Args:
            jobs: List of SlurmJob objects

        Returns:
            Dictionary mapping job_id to resolved log path
        """
        result = {}
        for job in jobs:
            # Extract project name from work_dir if available
            project_name = self._extract_project_name(job.work_dir)

            path = self.resolve_path(
                job_id=job.job_id,
                work_dir=job.work_dir,
                project_name=project_name,
            )
            result[job.job_id] = path

        return result

    def _extract_project_name(self, work_dir: Optional[str]) -> Optional[str]:
        """
        Extract project name from work directory path.

        Looks for known project patterns in specific_projects config.

        Args:
            work_dir: The job's working directory

        Returns:
            Project name if found, None otherwise
        """
        if not work_dir:
            return None

        for project in self.config.log_paths.specific_projects.keys():
            if project in work_dir:
                return project

        return None


def resolve_log_path(
    job_id: str,
    work_dir: Optional[str] = None,
    project_name: Optional[str] = None,
    config: Optional[Config] = None,
) -> str:
    """
    Convenience function to resolve a single log path.

    Args:
        job_id: The Slurm job ID
        work_dir: The job's working directory
        project_name: Optional project name
        config: Optional config object

    Returns:
        Resolved log file path
    """
    resolver = LogPathResolver(config)
    return resolver.resolve_path(job_id, work_dir, project_name)


if __name__ == "__main__":
    import sys
    from slurm_monitor.config import ConfigLoader

    if len(sys.argv) < 2:
        print("Usage: python -m slurm_monitor.log_path_resolver <job_id> [work_dir] [project_name]")
        sys.exit(1)

    job_id = sys.argv[1]
    work_dir = sys.argv[2] if len(sys.argv) > 2 else None
    project_name = sys.argv[3] if len(sys.argv) > 3 else None

    try:
        config = ConfigLoader.load()
        resolver = LogPathResolver(config)

        path = resolver.resolve_path(job_id, work_dir, project_name)

        print(f"Job ID: {job_id}")
        print(f"Work Dir: {work_dir}")
        print(f"Project Name: {project_name}")
        print(f"Resolved Path: {path}")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
