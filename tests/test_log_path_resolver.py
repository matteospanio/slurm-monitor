"""Tests for log path resolver."""

import pytest

from slurmhub.config import LogConfig
from slurmhub.log_path_resolver import LogPathResolver, resolve_log_path
from slurmhub.squeue_parser import SlurmJob


class TestLogPathResolver:
    """Test suite for LogPathResolver class."""

    def test_default_pattern_basic(self):
        resolver = LogPathResolver(LogConfig())
        path = resolver.resolve_path(job_id="12345", work_dir="/home/user/project")
        assert path == "/home/user/project/logs/12345.out"

    def test_default_pattern_without_workdir(self):
        resolver = LogPathResolver(LogConfig())
        path = resolver.resolve_path(job_id="12345")
        assert path == "{work_dir}/logs/12345.out"

    def test_custom_default_pattern(self):
        log_config = LogConfig(default_pattern="{work_dir}/output/{job_id}.log")
        resolver = LogPathResolver(log_config)
        path = resolver.resolve_path(job_id="12345", work_dir="/home/user/project")
        assert path == "/home/user/project/output/12345.log"

    def test_specific_project_by_name(self):
        log_config = LogConfig(
            specific_projects={"ml_project": "{work_dir}/ml/logs/{job_id}.txt"},
        )
        resolver = LogPathResolver(log_config)
        path = resolver.resolve_path(
            job_id="12345",
            work_dir="/home/user/ml_project",
            project_name="ml_project",
        )
        assert path == "/home/user/ml_project/ml/logs/12345.txt"

    def test_specific_project_from_workdir(self):
        log_config = LogConfig(
            specific_projects={
                "ml_project": "{work_dir}/ml/logs/{job_id}.txt",
                "sim_project": "{work_dir}/simulations/output/{job_id}.log",
            },
        )
        resolver = LogPathResolver(log_config)
        path = resolver.resolve_path(
            job_id="12345", work_dir="/home/user/ml_project/experiments"
        )
        assert path == "/home/user/ml_project/experiments/ml/logs/12345.txt"

    def test_explicit_project_name_priority(self):
        log_config = LogConfig(
            specific_projects={
                "project_a": "{work_dir}/a/{job_id}.log",
                "project_b": "{work_dir}/b/{job_id}.log",
            },
        )
        resolver = LogPathResolver(log_config)
        path = resolver.resolve_path(
            job_id="12345",
            work_dir="/home/user/project_b",
            project_name="project_a",
        )
        assert path == "/home/user/project_b/a/12345.log"

    def test_no_matching_project_uses_default(self):
        log_config = LogConfig(
            specific_projects={"special": "{work_dir}/special/{job_id}.txt"},
        )
        resolver = LogPathResolver(log_config)
        path = resolver.resolve_path(
            job_id="12345", work_dir="/home/user/other_project"
        )
        assert path == "/home/user/other_project/logs/12345.out"

    def test_all_tokens_replaced(self):
        log_config = LogConfig(
            default_pattern="{work_dir}/{project_name}/logs/{job_id}.out"
        )
        resolver = LogPathResolver(log_config)
        path = resolver.resolve_path(
            job_id="12345",
            work_dir="/home/user/project",
            project_name="my_experiment",
        )
        assert path == "/home/user/project/my_experiment/logs/12345.out"

    def test_project_name_token_without_value(self):
        log_config = LogConfig(
            default_pattern="{work_dir}/{project_name}/logs/{job_id}.out"
        )
        resolver = LogPathResolver(log_config)
        path = resolver.resolve_path(job_id="12345", work_dir="/home/user/project")
        assert path == "/home/user/project/{project_name}/logs/12345.out"

    def test_resolve_paths_for_jobs(self):
        resolver = LogPathResolver(LogConfig())
        jobs = [
            SlurmJob("12345", "job1", "RUNNING", "01:23:45", "/home/user/proj1"),
            SlurmJob("12346", "job2", "RUNNING", "00:30:00", "/home/user/proj2"),
            SlurmJob("12347", "job3", "PENDING", "00:00:00", None),
        ]
        paths = resolver.resolve_paths_for_jobs(jobs)
        assert len(paths) == 3
        assert paths["12345"] == "/home/user/proj1/logs/12345.out"
        assert paths["12347"] == "{work_dir}/logs/12347.out"

    def test_resolve_paths_with_specific_projects(self):
        log_config = LogConfig(
            specific_projects={"ml_project": "{work_dir}/ml/output/{job_id}.log"},
        )
        resolver = LogPathResolver(log_config)
        jobs = [
            SlurmJob("12345", "j1", "RUNNING", "01:00:00", "/home/user/ml_project"),
            SlurmJob("12346", "j2", "RUNNING", "00:30:00", "/home/user/other_proj"),
        ]
        paths = resolver.resolve_paths_for_jobs(jobs)
        assert paths["12345"] == "/home/user/ml_project/ml/output/12345.log"
        assert paths["12346"] == "/home/user/other_proj/logs/12346.out"

    def test_extract_project_name_found(self):
        log_config = LogConfig(
            specific_projects={
                "ml_project": "{work_dir}/ml/{job_id}.log",
                "sim_project": "{work_dir}/sim/{job_id}.log",
            }
        )
        resolver = LogPathResolver(log_config)
        assert resolver._extract_project_name("/home/user/ml_project/exp1") == "ml_project"

    def test_extract_project_name_not_found(self):
        log_config = LogConfig(
            specific_projects={"ml_project": "{work_dir}/ml/{job_id}.log"},
        )
        resolver = LogPathResolver(log_config)
        assert resolver._extract_project_name("/home/user/other") is None

    def test_extract_project_name_none_workdir(self):
        resolver = LogPathResolver(LogConfig())
        assert resolver._extract_project_name(None) is None

    def test_complex_path_pattern(self):
        log_config = LogConfig(
            default_pattern="{work_dir}/runs/{project_name}/output/job_{job_id}/stdout.log"
        )
        resolver = LogPathResolver(log_config)
        path = resolver.resolve_path(
            job_id="12345",
            work_dir="/scratch/user/experiments",
            project_name="exp_2024",
        )
        assert path == "/scratch/user/experiments/runs/exp_2024/output/job_12345/stdout.log"

    def test_resolve_view_command(self):
        log_config = LogConfig(view_command="less +F {log_path}")
        resolver = LogPathResolver(log_config)
        cmd = resolver.resolve_view_command(
            job_id="12345", work_dir="/home/user/project"
        )
        assert cmd == "less +F /home/user/project/logs/12345.out"

    def test_resolve_view_command_default(self):
        resolver = LogPathResolver(LogConfig())
        cmd = resolver.resolve_view_command(
            job_id="12345", work_dir="/home/user/project"
        )
        assert cmd == "tail -f /home/user/project/logs/12345.out"


class TestResolveLogPathFunction:
    """Test suite for resolve_log_path convenience function."""

    def test_convenience_function_basic(self):
        log_config = LogConfig(default_pattern="{work_dir}/logs/{job_id}.out")
        path = resolve_log_path(
            job_id="12345",
            work_dir="/home/user/project",
            log_config=log_config,
        )
        assert path == "/home/user/project/logs/12345.out"

    def test_convenience_function_with_project(self):
        log_config = LogConfig(
            specific_projects={"ml": "{work_dir}/ml/{job_id}.log"},
        )
        path = resolve_log_path(
            job_id="12345",
            work_dir="/home/user/ml",
            project_name="ml",
            log_config=log_config,
        )
        assert path == "/home/user/ml/ml/12345.log"

    def test_convenience_function_default_config(self):
        path = resolve_log_path(job_id="12345", work_dir="/home/user/project")
        assert "12345" in path
        assert "logs" in path
