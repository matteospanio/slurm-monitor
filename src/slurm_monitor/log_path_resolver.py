"""Log path resolution strategy for Slurm jobs."""

from typing import Optional

from slurm_monitor.config import LogConfig, ProfileConfig


class LogPathResolver:
    """Resolves log file paths based on configuration patterns.

    Supports token replacement and project-specific patterns.
    """

    def __init__(self, log_config: LogConfig):
        """Initialize the path resolver.

        Args:
            log_config: Log configuration with patterns.
        """
        self.log_config = log_config

    def resolve_path(
        self,
        job_id: str,
        work_dir: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> str:
        """Resolve the log file path for a job.

        Resolution strategy:
        1. Check if explicit project_name matches a specific pattern
        2. Check if work_dir matches a specific project pattern
        3. Fall back to default pattern
        4. Replace tokens: {job_id}, {work_dir}, {project_name}

        Args:
            job_id: The Slurm job ID
            work_dir: The job's working directory
            project_name: Optional project name for specific patterns

        Returns:
            Resolved log file path as string
        """
        pattern = self._get_pattern(work_dir, project_name)

        resolved = pattern
        resolved = resolved.replace("{job_id}", job_id)

        if work_dir:
            resolved = resolved.replace("{work_dir}", work_dir)

        if project_name:
            resolved = resolved.replace("{project_name}", project_name)

        return resolved

    def resolve_view_command(
        self,
        job_id: str,
        work_dir: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> str:
        """Resolve the full log view command for a job.

        Args:
            job_id: The Slurm job ID
            work_dir: The job's working directory
            project_name: Optional project name

        Returns:
            Resolved view command string (e.g. "tail -f /path/to/log")
        """
        log_path = self.resolve_path(job_id, work_dir, project_name)
        return self.log_config.view_command.replace("{log_path}", log_path)

    def _get_pattern(
        self,
        work_dir: Optional[str],
        project_name: Optional[str],
    ) -> str:
        """Get the appropriate pattern based on work_dir or project_name."""
        # First priority: explicit project_name
        if project_name and project_name in self.log_config.specific_projects:
            return self.log_config.specific_projects[project_name]

        # Second priority: check if work_dir matches a project
        if work_dir:
            for project, pattern in self.log_config.specific_projects.items():
                if project in work_dir:
                    return pattern

        return self.log_config.default_pattern

    def resolve_paths_for_jobs(self, jobs: list) -> dict[str, str]:
        """Resolve log paths for multiple jobs.

        Args:
            jobs: List of SlurmJob objects

        Returns:
            Dictionary mapping job_id to resolved log path
        """
        result = {}
        for job in jobs:
            project_name = self._extract_project_name(job.work_dir)
            path = self.resolve_path(
                job_id=job.job_id,
                work_dir=job.work_dir,
                project_name=project_name,
            )
            result[job.job_id] = path
        return result

    def _extract_project_name(self, work_dir: Optional[str]) -> Optional[str]:
        """Extract project name from work directory path."""
        if not work_dir:
            return None

        for project in self.log_config.specific_projects.keys():
            if project in work_dir:
                return project

        return None


def resolve_log_path(
    job_id: str,
    work_dir: Optional[str] = None,
    project_name: Optional[str] = None,
    log_config: Optional[LogConfig] = None,
) -> str:
    """Convenience function to resolve a single log path.

    Args:
        job_id: The Slurm job ID
        work_dir: The job's working directory
        project_name: Optional project name
        log_config: Optional log config object

    Returns:
        Resolved log file path
    """
    resolver = LogPathResolver(log_config or LogConfig())
    return resolver.resolve_path(job_id, work_dir, project_name)
