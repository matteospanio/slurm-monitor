"""Tests for configuration loader."""

import json
from pathlib import Path

import pytest

from slurm_monitor.config import (
    AppConfig,
    ConfigLoader,
    LogConfig,
    ProfileConfig,
    SSHConfig,
    SlurmConfig,
    _from_legacy_json,
    _from_toml_dict,
)


class TestSSHConfig:
    """Test suite for SSHConfig dataclass."""

    def test_default_values(self):
        config = SSHConfig()
        assert config.host == "localhost"
        assert config.port == 22
        assert config.username == ""
        assert config.key_filename == ""
        assert config.jump_host == ""

    def test_custom_values(self):
        config = SSHConfig(
            host="cluster.edu",
            port=2222,
            username="matteo",
            key_filename="~/.ssh/id_rsa",
            jump_host="bastion.edu",
        )
        assert config.host == "cluster.edu"
        assert config.port == 2222
        assert config.username == "matteo"


class TestLogConfig:
    """Test suite for LogConfig dataclass."""

    def test_default_values(self):
        config = LogConfig()
        assert config.default_pattern == "{work_dir}/logs/{job_id}.out"
        assert config.specific_projects == {}
        assert config.view_command == "tail -f {log_path}"

    def test_custom_values(self):
        config = LogConfig(
            default_pattern="{work_dir}/output/{job_id}.log",
            specific_projects={"proj1": "{work_dir}/custom/{job_id}.out"},
            view_command="less +F {log_path}",
        )
        assert config.default_pattern == "{work_dir}/output/{job_id}.log"
        assert "proj1" in config.specific_projects
        assert config.view_command == "less +F {log_path}"


class TestSlurmConfig:
    """Test suite for SlurmConfig dataclass."""

    def test_default_values(self):
        config = SlurmConfig()
        assert config.squeue_format == "%i|%j|%T|%M|%Z"
        assert config.sacct_format == "JobID,JobName,State,Elapsed,WorkDir"


class TestProfileConfig:
    """Test suite for ProfileConfig dataclass."""

    def test_default_values(self):
        profile = ProfileConfig()
        assert profile.name == "default"
        assert profile.ssh.host == "localhost"
        assert profile.refresh_interval == 5
        assert profile.sacct_refresh_interval == 60
        assert profile.ssh_timeout == 10

    def test_custom_values(self):
        profile = ProfileConfig(
            name="hpc",
            ssh=SSHConfig(host="hpc.edu"),
            refresh_interval=10,
            ssh_timeout=30,
        )
        assert profile.name == "hpc"
        assert profile.ssh.host == "hpc.edu"
        assert profile.refresh_interval == 10


class TestAppConfig:
    """Test suite for AppConfig dataclass."""

    def test_empty_profiles(self):
        config = AppConfig()
        assert config.profiles == {}
        assert config.profile_names == []

    def test_get_profile(self):
        profile = ProfileConfig(name="test", ssh=SSHConfig(host="test.edu"))
        config = AppConfig(profiles={"test": profile})
        assert config.get_profile("test") is profile

    def test_get_profile_not_found(self):
        config = AppConfig(profiles={})
        with pytest.raises(KeyError, match="Profile 'missing' not found"):
            config.get_profile("missing")

    def test_profile_names(self):
        config = AppConfig(
            profiles={
                "a": ProfileConfig(name="a"),
                "b": ProfileConfig(name="b"),
            }
        )
        assert config.profile_names == ["a", "b"]


class TestFromTomlDict:
    """Test parsing TOML dictionaries into AppConfig."""

    def test_minimal_config(self):
        data = {
            "profiles": {
                "cluster": {"host": "cluster.edu"},
            }
        }
        config = _from_toml_dict(data)
        assert "cluster" in config.profiles
        assert config.profiles["cluster"].ssh.host == "cluster.edu"

    def test_defaults_are_inherited(self):
        data = {
            "defaults": {
                "ssh_timeout": 30,
                "refresh_interval": 10,
                "ssh": {"username": "matteo", "port": 2222},
                "log": {"default_pattern": "{work_dir}/out/{job_id}.log"},
            },
            "profiles": {
                "a": {"host": "a.edu"},
                "b": {"host": "b.edu"},
            },
        }
        config = _from_toml_dict(data)
        for name in ("a", "b"):
            p = config.profiles[name]
            assert p.ssh_timeout == 30
            assert p.refresh_interval == 10
            assert p.ssh.username == "matteo"
            assert p.ssh.port == 2222
            assert p.log.default_pattern == "{work_dir}/out/{job_id}.log"

    def test_profile_overrides_defaults(self):
        data = {
            "defaults": {
                "ssh_timeout": 30,
                "ssh": {"username": "default_user"},
            },
            "profiles": {
                "special": {
                    "host": "special.edu",
                    "ssh_timeout": 60,
                    "ssh": {"username": "override_user"},
                },
            },
        }
        config = _from_toml_dict(data)
        p = config.profiles["special"]
        assert p.ssh_timeout == 60
        assert p.ssh.username == "override_user"

    def test_no_profiles_creates_default(self):
        data = {
            "defaults": {
                "ssh": {"host": "my-cluster.edu"},
            }
        }
        config = _from_toml_dict(data)
        assert "default" in config.profiles
        assert config.profiles["default"].ssh.host == "my-cluster.edu"

    def test_empty_data_creates_default(self):
        config = _from_toml_dict({})
        assert "default" in config.profiles
        assert config.profiles["default"].ssh.host == "localhost"

    def test_specific_projects_merged(self):
        data = {
            "defaults": {
                "log": {
                    "specific_projects": {"global_proj": "{work_dir}/g/{job_id}.out"},
                },
            },
            "profiles": {
                "cluster": {
                    "host": "cluster.edu",
                    "log": {
                        "specific_projects": {
                            "local_proj": "{work_dir}/l/{job_id}.out"
                        },
                    },
                },
            },
        }
        config = _from_toml_dict(data)
        projects = config.profiles["cluster"].log.specific_projects
        assert "global_proj" in projects
        assert "local_proj" in projects

    def test_slurm_config_override(self):
        data = {
            "defaults": {
                "slurm": {"squeue_format": "%i|%j|%T|%M|%Z|%P"},
            },
            "profiles": {
                "cluster": {"host": "c.edu"},
            },
        }
        config = _from_toml_dict(data)
        assert (
            config.profiles["cluster"].slurm.squeue_format == "%i|%j|%T|%M|%Z|%P"
        )

    def test_host_in_ssh_section(self):
        """Host can be specified inside ssh section instead of top-level."""
        data = {
            "profiles": {
                "cluster": {"ssh": {"host": "cluster.edu"}},
            }
        }
        config = _from_toml_dict(data)
        assert config.profiles["cluster"].ssh.host == "cluster.edu"

    def test_multiple_profiles(self):
        data = {
            "profiles": {
                "a": {"host": "a.edu"},
                "b": {"host": "b.edu"},
                "c": {"host": "c.edu"},
            }
        }
        config = _from_toml_dict(data)
        assert len(config.profiles) == 3
        assert config.profiles["a"].ssh.host == "a.edu"
        assert config.profiles["b"].ssh.host == "b.edu"
        assert config.profiles["c"].ssh.host == "c.edu"


class TestFromLegacyJson:
    """Test backward-compatible JSON config loading."""

    def test_full_legacy_config(self):
        data = {
            "remote_host": "cluster.example.com",
            "ssh_timeout": 30,
            "refresh_interval": 5,
            "log_paths": {
                "default_pattern": "{work_dir}/output/{job_id}.log",
                "specific_projects": {
                    "proj1": "{work_dir}/proj1/{job_id}.out",
                    "proj2": "{work_dir}/proj2/{job_id}.log",
                },
            },
        }
        config = _from_legacy_json(data)
        assert "default" in config.profiles
        p = config.profiles["default"]
        assert p.ssh.host == "cluster.example.com"
        assert p.ssh_timeout == 30
        assert p.refresh_interval == 5
        assert p.log.default_pattern == "{work_dir}/output/{job_id}.log"
        assert len(p.log.specific_projects) == 2

    def test_partial_legacy_config(self):
        data = {"remote_host": "cluster.example.com"}
        config = _from_legacy_json(data)
        p = config.profiles["default"]
        assert p.ssh.host == "cluster.example.com"
        assert p.ssh_timeout == 10
        assert p.refresh_interval == 5

    def test_empty_legacy_config(self):
        config = _from_legacy_json({})
        p = config.profiles["default"]
        assert p.ssh.host == "localhost"
        assert p.ssh_timeout == 10


class TestConfigLoader:
    """Test suite for ConfigLoader class."""

    def test_load_returns_defaults_when_no_config(self, monkeypatch):
        monkeypatch.setattr(
            ConfigLoader, "DEFAULT_CONFIG_PATHS", [Path("/nonexistent/config.toml")]
        )
        config = ConfigLoader.load()
        assert "default" in config.profiles
        assert config.profiles["default"].ssh.host == "localhost"

    def test_load_toml_file(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[profiles.test]\nhost = "test.cluster.com"\nssh_timeout = 25\n'
        )
        config = ConfigLoader.load(config_file)
        assert "test" in config.profiles
        assert config.profiles["test"].ssh.host == "test.cluster.com"
        assert config.profiles["test"].ssh_timeout == 25

    def test_load_json_file_backward_compat(self, tmp_path):
        config_file = tmp_path / "config.json"
        data = {"remote_host": "legacy.cluster.com", "ssh_timeout": 25}
        with open(config_file, "w") as f:
            json.dump(data, f)
        config = ConfigLoader.load(config_file)
        p = config.profiles["default"]
        assert p.ssh.host == "legacy.cluster.com"
        assert p.ssh_timeout == 25

    def test_load_nonexistent_file_raises(self, tmp_path):
        config_file = tmp_path / "nonexistent.toml"
        with pytest.raises(FileNotFoundError):
            ConfigLoader.load(config_file)

    def test_load_invalid_toml_raises(self, tmp_path):
        config_file = tmp_path / "invalid.toml"
        config_file.write_text("{{invalid toml}}")
        with pytest.raises(ValueError, match="Invalid TOML"):
            ConfigLoader.load(config_file)

    def test_load_invalid_json_raises(self, tmp_path):
        config_file = tmp_path / "invalid.json"
        config_file.write_text("{ invalid json }")
        with pytest.raises(ValueError, match="Invalid JSON"):
            ConfigLoader.load(config_file)

    def test_load_unsupported_format_raises(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: value")
        with pytest.raises(ValueError, match="Unsupported config format"):
            ConfigLoader.load(config_file)

    def test_load_searches_default_paths(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[profiles.found]\nhost = "found.cluster.com"\n'
        )
        test_paths = [Path("/nonexistent/config.toml"), config_file]
        monkeypatch.setattr(ConfigLoader, "DEFAULT_CONFIG_PATHS", test_paths)
        config = ConfigLoader.load()
        assert "found" in config.profiles

    def test_load_skips_invalid_default_configs(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.toml"
        config_file.write_text("{{invalid}}")
        test_paths = [config_file]
        monkeypatch.setattr(ConfigLoader, "DEFAULT_CONFIG_PATHS", test_paths)
        config = ConfigLoader.load()
        assert "default" in config.profiles
        assert config.profiles["default"].ssh.host == "localhost"

    def test_load_complete_toml_config(self, tmp_path):
        config_file = tmp_path / "complete.toml"
        config_file.write_text(
            """
[defaults]
ssh_timeout = 30
refresh_interval = 10
sacct_refresh_interval = 120

[defaults.ssh]
username = "matteo"

[defaults.log]
default_pattern = "{work_dir}/out/{job_id}.log"
view_command = "less +F {log_path}"

[defaults.slurm]
squeue_format = "%i|%j|%T|%M|%Z|%P"

[profiles.hpc]
host = "hpc.edu"
ssh.key_filename = "~/.ssh/id_hpc"
log.specific_projects.ml = "{work_dir}/ml/{job_id}.out"

[profiles.cloud]
host = "cloud.edu"
ssh.jump_host = "bastion.edu"
ssh_timeout = 60
"""
        )
        config = ConfigLoader.load(config_file)
        assert len(config.profiles) == 2

        hpc = config.profiles["hpc"]
        assert hpc.ssh.host == "hpc.edu"
        assert hpc.ssh.username == "matteo"  # inherited
        assert hpc.ssh.key_filename == "~/.ssh/id_hpc"
        assert hpc.ssh_timeout == 30  # inherited
        assert hpc.refresh_interval == 10  # inherited
        assert hpc.log.default_pattern == "{work_dir}/out/{job_id}.log"  # inherited
        assert hpc.log.view_command == "less +F {log_path}"  # inherited
        assert hpc.slurm.squeue_format == "%i|%j|%T|%M|%Z|%P"  # inherited
        assert "ml" in hpc.log.specific_projects

        cloud = config.profiles["cloud"]
        assert cloud.ssh.host == "cloud.edu"
        assert cloud.ssh.jump_host == "bastion.edu"
        assert cloud.ssh_timeout == 60  # overridden

    def test_save_toml(self, tmp_path):
        config_file = tmp_path / "saved.toml"
        profile = ProfileConfig(
            name="test",
            ssh=SSHConfig(host="save.test.com", username="user"),
            ssh_timeout=20,
        )
        app_config = AppConfig(profiles={"test": profile})
        ConfigLoader.save_toml(app_config, config_file)
        assert config_file.exists()
        content = config_file.read_text()
        assert "save.test.com" in content
        assert "user" in content

    def test_save_creates_parent_directories(self, tmp_path):
        config_file = tmp_path / "nested" / "dir" / "config.toml"
        app_config = AppConfig(
            profiles={"default": ProfileConfig(name="default")}
        )
        ConfigLoader.save_toml(app_config, config_file)
        assert config_file.exists()
        assert config_file.parent.exists()

    def test_get_default_config_path(self):
        path = ConfigLoader.get_default_config_path()
        assert path == Path.home() / ".config" / "slurm_monitor" / "config.toml"
        assert isinstance(path, Path)

    def test_default_paths_include_toml_and_json(self):
        paths = ConfigLoader.DEFAULT_CONFIG_PATHS
        extensions = [p.suffix for p in paths]
        assert ".toml" in extensions
        assert ".json" in extensions
