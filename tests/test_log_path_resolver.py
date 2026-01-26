"""Tests for log path resolver."""

import pytest

from slurm_monitor.config import Config, LogPathConfig
from slurm_monitor.log_path_resolver import LogPathResolver, resolve_log_path
from slurm_monitor.squeue_parser import SlurmJob


class TestLogPathResolver:
    """Test suite for LogPathResolver class."""

    def test_default_pattern_basic(self):
        """Test resolution with default pattern."""
        config = Config()
        resolver = LogPathResolver(config)

        path = resolver.resolve_path(
            job_id="12345", work_dir="/home/user/project"
        )

        assert path == "/home/user/project/logs/12345.out"

    def test_default_pattern_without_workdir(self):
        """Test resolution without work_dir."""
        config = Config()
        resolver = LogPathResolver(config)

        path = resolver.resolve_path(job_id="12345")

        # {work_dir} token remains unreplaced
        assert path == "{work_dir}/logs/12345.out"

    def test_custom_default_pattern(self):
        """Test resolution with custom default pattern."""
        log_paths = LogPathConfig(
            default_pattern="{work_dir}/output/{job_id}.log"
        )
        config = Config(log_paths=log_paths)
        resolver = LogPathResolver(config)

        path = resolver.resolve_path(
            job_id="12345", work_dir="/home/user/project"
        )

        assert path == "/home/user/project/output/12345.log"

    def test_specific_project_by_name(self):
        """Test resolution using specific project pattern by name."""
        log_paths = LogPathConfig(
            default_pattern="{work_dir}/logs/{job_id}.out",
            specific_projects={
                "ml_project": "{work_dir}/ml/logs/{job_id}.txt",
            },
        )
        config = Config(log_paths=log_paths)
        resolver = LogPathResolver(config)

        path = resolver.resolve_path(
            job_id="12345",
            work_dir="/home/user/ml_project",
            project_name="ml_project",
        )

        assert path == "/home/user/ml_project/ml/logs/12345.txt"

    def test_specific_project_from_workdir(self):
        """Test resolution using specific project detected from work_dir."""
        log_paths = LogPathConfig(
            default_pattern="{work_dir}/logs/{job_id}.out",
            specific_projects={
                "ml_project": "{work_dir}/ml/logs/{job_id}.txt",
                "sim_project": "{work_dir}/simulations/output/{job_id}.log",
            },
        )
        config = Config(log_paths=log_paths)
        resolver = LogPathResolver(config)

        # Project name in work_dir should be detected
        path = resolver.resolve_path(
            job_id="12345", work_dir="/home/user/ml_project/experiments"
        )

        assert path == "/home/user/ml_project/experiments/ml/logs/12345.txt"

    def test_explicit_project_name_priority(self):
        """Test that explicit project_name takes priority."""
        log_paths = LogPathConfig(
            default_pattern="{work_dir}/logs/{job_id}.out",
            specific_projects={
                "project_a": "{work_dir}/a/{job_id}.log",
                "project_b": "{work_dir}/b/{job_id}.log",
            },
        )
        config = Config(log_paths=log_paths)
        resolver = LogPathResolver(config)

        # Even though work_dir contains project_b, explicit project_a should win
        path = resolver.resolve_path(
            job_id="12345",
            work_dir="/home/user/project_b",
            project_name="project_a",
        )

        assert path == "/home/user/project_b/a/12345.log"

    def test_no_matching_project_uses_default(self):
        """Test that non-matching project uses default pattern."""
        log_paths = LogPathConfig(
            default_pattern="{work_dir}/logs/{job_id}.out",
            specific_projects={
                "special_project": "{work_dir}/special/{job_id}.txt",
            },
        )
        config = Config(log_paths=log_paths)
        resolver = LogPathResolver(config)

        path = resolver.resolve_path(
            job_id="12345", work_dir="/home/user/other_project"
        )

        assert path == "/home/user/other_project/logs/12345.out"

    def test_all_tokens_replaced(self):
        """Test that all tokens are replaced correctly."""
        log_paths = LogPathConfig(
            default_pattern="{work_dir}/{project_name}/logs/{job_id}.out"
        )
        config = Config(log_paths=log_paths)
        resolver = LogPathResolver(config)

        path = resolver.resolve_path(
            job_id="12345",
            work_dir="/home/user/project",
            project_name="my_experiment",
        )

        assert path == "/home/user/project/my_experiment/logs/12345.out"

    def test_project_name_token_without_value(self):
        """Test that {project_name} remains if no project_name provided."""
        log_paths = LogPathConfig(
            default_pattern="{work_dir}/{project_name}/logs/{job_id}.out"
        )
        config = Config(log_paths=log_paths)
        resolver = LogPathResolver(config)

        path = resolver.resolve_path(
            job_id="12345", work_dir="/home/user/project"
        )

        assert path == "/home/user/project/{project_name}/logs/12345.out"

    def test_resolve_paths_for_jobs(self):
        """Test resolving paths for multiple jobs."""
        log_paths = LogPathConfig(
            default_pattern="{work_dir}/logs/{job_id}.out"
        )
        config = Config(log_paths=log_paths)
        resolver = LogPathResolver(config)

        jobs = [
            SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user/proj1"),
            SlurmJob("12346", "job2", "RUNNING", "00:30:00", "/home/user/proj2"),
            SlurmJob("12347", "job3", "PENDING", "00:00:00", None),
        ]

        paths = resolver.resolve_paths_for_jobs(jobs)

        assert len(paths) == 3
        assert paths["12345"] == "/home/user/proj1/logs/12345.out"
        assert paths["12346"] == "/home/user/proj2/logs/12346.out"
        assert paths["12347"] == "{work_dir}/logs/12347.out"

    def test_resolve_paths_with_specific_projects(self):
        """Test resolving paths with project-specific patterns."""
        log_paths = LogPathConfig(
            default_pattern="{work_dir}/logs/{job_id}.out",
            specific_projects={
                "ml_project": "{work_dir}/ml/output/{job_id}.log",
            },
        )
        config = Config(log_paths=log_paths)
        resolver = LogPathResolver(config)

        jobs = [
            SlurmJob(
                "12345", "job1", "RUNNING", "01:23:45", "/home/user/ml_project"
            ),
            SlurmJob(
                "12346", "job2", "RUNNING", "00:30:00", "/home/user/other_proj"
            ),
        ]

        paths = resolver.resolve_paths_for_jobs(jobs)

        assert paths["12345"] == "/home/user/ml_project/ml/output/12345.log"
        assert paths["12346"] == "/home/user/other_proj/logs/12346.out"

    def test_extract_project_name_found(self):
        """Test extracting project name from work_dir."""
        log_paths = LogPathConfig(
            specific_projects={
                "ml_project": "{work_dir}/ml/{job_id}.log",
                "sim_project": "{work_dir}/sim/{job_id}.log",
            }
        )
        config = Config(log_paths=log_paths)
        resolver = LogPathResolver(config)

        project = resolver._extract_project_name("/home/user/ml_project/exp1")

        assert project == "ml_project"

    def test_extract_project_name_not_found(self):
        """Test extracting project name when not found."""
        log_paths = LogPathConfig(
            specific_projects={
                "ml_project": "{work_dir}/ml/{job_id}.log",
            }
        )
        config = Config(log_paths=log_paths)
        resolver = LogPathResolver(config)

        project = resolver._extract_project_name("/home/user/other_project")

        assert project is None

    def test_extract_project_name_none_workdir(self):
        """Test extracting project name from None work_dir."""
        config = Config()
        resolver = LogPathResolver(config)

        project = resolver._extract_project_name(None)

        assert project is None

    def test_complex_path_pattern(self):
        """Test complex path pattern with nested directories."""
        log_paths = LogPathConfig(
            default_pattern="{work_dir}/runs/{project_name}/output/job_{job_id}/stdout.log"
        )
        config = Config(log_paths=log_paths)
        resolver = LogPathResolver(config)

        path = resolver.resolve_path(
            job_id="12345",
            work_dir="/scratch/user/experiments",
            project_name="exp_2024",
        )

        assert (
            path
            == "/scratch/user/experiments/runs/exp_2024/output/job_12345/stdout.log"
        )


class TestResolveLogPathFunction:
    """Test suite for resolve_log_path convenience function."""

    def test_convenience_function_basic(self):
        """Test convenience function with basic usage."""
        config = Config(
            log_paths=LogPathConfig(
                default_pattern="{work_dir}/logs/{job_id}.out"
            )
        )

        path = resolve_log_path(
            job_id="12345", work_dir="/home/user/project", config=config
        )

        assert path == "/home/user/project/logs/12345.out"

    def test_convenience_function_with_project(self):
        """Test convenience function with project name."""
        config = Config(
            log_paths=LogPathConfig(
                default_pattern="{work_dir}/logs/{job_id}.out",
                specific_projects={
                    "ml": "{work_dir}/ml/{job_id}.log",
                },
            )
        )

        path = resolve_log_path(
            job_id="12345",
            work_dir="/home/user/ml",
            project_name="ml",
            config=config,
        )

        assert path == "/home/user/ml/ml/12345.log"

    def test_convenience_function_loads_default_config(self):
        """Test convenience function loads default config if none provided."""
        # Should not raise an error
        path = resolve_log_path(job_id="12345", work_dir="/home/user/project")

        # Should use default pattern
        assert "12345" in path
        assert "logs" in path
