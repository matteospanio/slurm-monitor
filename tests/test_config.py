"""Tests for configuration loader."""

import json
import tempfile
from pathlib import Path

import pytest

from slurm_monitor.config import Config, ConfigLoader, LogPathConfig


class TestLogPathConfig:
    """Test suite for LogPathConfig dataclass."""

    def test_default_values(self):
        """Test default LogPathConfig values."""
        config = LogPathConfig()

        assert config.default_pattern == "{work_dir}/logs/{job_id}.out"
        assert config.specific_projects == {}

    def test_custom_values(self):
        """Test custom LogPathConfig values."""
        config = LogPathConfig(
            default_pattern="{work_dir}/output/{job_id}.log",
            specific_projects={"project1": "{work_dir}/custom/{job_id}.out"},
        )

        assert config.default_pattern == "{work_dir}/output/{job_id}.log"
        assert config.specific_projects == {
            "project1": "{work_dir}/custom/{job_id}.out"
        }


class TestConfig:
    """Test suite for Config dataclass."""

    def test_default_values(self):
        """Test default Config values."""
        config = Config()

        assert config.remote_host == "localhost"
        assert config.ssh_timeout == 10
        assert config.refresh_interval == 2
        assert config.log_paths.default_pattern == "{work_dir}/logs/{job_id}.out"

    def test_custom_values(self):
        """Test custom Config values."""
        log_paths = LogPathConfig(default_pattern="{work_dir}/custom/{job_id}.log")
        config = Config(
            remote_host="cluster.example.com",
            ssh_timeout=30,
            refresh_interval=5,
            log_paths=log_paths,
        )

        assert config.remote_host == "cluster.example.com"
        assert config.ssh_timeout == 30
        assert config.refresh_interval == 5
        assert config.log_paths.default_pattern == "{work_dir}/custom/{job_id}.log"

    def test_from_dict_full(self):
        """Test creating Config from complete dictionary."""
        data = {
            "remote_host": "cluster.example.com",
            "ssh_timeout": 30,
            "refresh_interval": 5,
            "log_paths": {
                "default_pattern": "{work_dir}/output/{job_id}.log",
                "specific_projects": {
                    "project1": "{work_dir}/proj1/{job_id}.out",
                    "project2": "{work_dir}/proj2/{job_id}.log",
                },
            },
        }

        config = Config.from_dict(data)

        assert config.remote_host == "cluster.example.com"
        assert config.ssh_timeout == 30
        assert config.refresh_interval == 5
        assert config.log_paths.default_pattern == "{work_dir}/output/{job_id}.log"
        assert len(config.log_paths.specific_projects) == 2

    def test_from_dict_partial(self):
        """Test creating Config from partial dictionary with defaults."""
        data = {"remote_host": "cluster.example.com"}

        config = Config.from_dict(data)

        assert config.remote_host == "cluster.example.com"
        assert config.ssh_timeout == 10  # default
        assert config.refresh_interval == 2  # default

    def test_from_dict_empty(self):
        """Test creating Config from empty dictionary uses all defaults."""
        data = {}

        config = Config.from_dict(data)

        assert config.remote_host == "localhost"
        assert config.ssh_timeout == 10
        assert config.refresh_interval == 2

    def test_to_dict(self):
        """Test converting Config to dictionary."""
        log_paths = LogPathConfig(
            default_pattern="{work_dir}/output/{job_id}.log",
            specific_projects={"project1": "{work_dir}/proj1/{job_id}.out"},
        )
        config = Config(
            remote_host="cluster.example.com",
            ssh_timeout=30,
            refresh_interval=5,
            log_paths=log_paths,
        )

        data = config.to_dict()

        assert data["remote_host"] == "cluster.example.com"
        assert data["ssh_timeout"] == 30
        assert data["refresh_interval"] == 5
        assert data["log_paths"]["default_pattern"] == "{work_dir}/output/{job_id}.log"
        assert "project1" in data["log_paths"]["specific_projects"]

    def test_roundtrip_conversion(self):
        """Test that to_dict/from_dict roundtrip preserves data."""
        original = Config(
            remote_host="cluster.example.com",
            ssh_timeout=30,
            refresh_interval=5,
            log_paths=LogPathConfig(
                default_pattern="{work_dir}/output/{job_id}.log",
                specific_projects={"project1": "{work_dir}/proj1/{job_id}.out"},
            ),
        )

        data = original.to_dict()
        restored = Config.from_dict(data)

        assert restored.remote_host == original.remote_host
        assert restored.ssh_timeout == original.ssh_timeout
        assert restored.refresh_interval == original.refresh_interval
        assert (
            restored.log_paths.default_pattern == original.log_paths.default_pattern
        )
        assert (
            restored.log_paths.specific_projects
            == original.log_paths.specific_projects
        )


class TestConfigLoader:
    """Test suite for ConfigLoader class."""

    def test_load_from_nonexistent_file_uses_defaults(self):
        """Test that loading with no config file returns defaults."""
        config = ConfigLoader.load()

        assert config.remote_host == "localhost"
        assert config.ssh_timeout == 10

    def test_load_from_specific_file(self, tmp_path):
        """Test loading from a specific file path."""
        config_file = tmp_path / "test_config.json"
        config_data = {
            "remote_host": "test.cluster.com",
            "ssh_timeout": 25,
        }

        with open(config_file, "w") as f:
            json.dump(config_data, f)

        config = ConfigLoader.load(config_file)

        assert config.remote_host == "test.cluster.com"
        assert config.ssh_timeout == 25

    def test_load_from_specific_file_not_found(self, tmp_path):
        """Test that loading from nonexistent specific file raises error."""
        config_file = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            ConfigLoader.load(config_file)

    def test_load_from_invalid_json(self, tmp_path):
        """Test that invalid JSON raises ValueError."""
        config_file = tmp_path / "invalid.json"

        with open(config_file, "w") as f:
            f.write("{ invalid json }")

        with pytest.raises(ValueError) as exc_info:
            ConfigLoader.load(config_file)

        assert "Invalid JSON" in str(exc_info.value)

    def test_load_with_complete_config(self, tmp_path):
        """Test loading complete configuration."""
        config_file = tmp_path / "complete.json"
        config_data = {
            "remote_host": "hpc.example.com",
            "ssh_timeout": 30,
            "refresh_interval": 5,
            "log_paths": {
                "default_pattern": "{work_dir}/logs/out/{job_id}.txt",
                "specific_projects": {
                    "ml_project": "{work_dir}/ml/logs/{job_id}.out",
                    "sim_project": "{work_dir}/simulations/output/{job_id}.log",
                },
            },
        }

        with open(config_file, "w") as f:
            json.dump(config_data, f)

        config = ConfigLoader.load(config_file)

        assert config.remote_host == "hpc.example.com"
        assert config.ssh_timeout == 30
        assert config.refresh_interval == 5
        assert config.log_paths.default_pattern == "{work_dir}/logs/out/{job_id}.txt"
        assert len(config.log_paths.specific_projects) == 2
        assert (
            config.log_paths.specific_projects["ml_project"]
            == "{work_dir}/ml/logs/{job_id}.out"
        )

    def test_save_config(self, tmp_path):
        """Test saving configuration to file."""
        config_file = tmp_path / "saved_config.json"
        config = Config(
            remote_host="save.test.com",
            ssh_timeout=20,
            refresh_interval=3,
        )

        ConfigLoader.save(config, config_file)

        assert config_file.exists()

        # Verify content
        with open(config_file, "r") as f:
            data = json.load(f)

        assert data["remote_host"] == "save.test.com"
        assert data["ssh_timeout"] == 20
        assert data["refresh_interval"] == 3

    def test_save_creates_parent_directories(self, tmp_path):
        """Test that save creates parent directories if needed."""
        config_file = tmp_path / "nested" / "dir" / "config.json"
        config = Config(remote_host="nested.test.com")

        ConfigLoader.save(config, config_file)

        assert config_file.exists()
        assert config_file.parent.exists()

    def test_save_and_load_roundtrip(self, tmp_path):
        """Test that saving and loading preserves configuration."""
        config_file = tmp_path / "roundtrip.json"
        original = Config(
            remote_host="roundtrip.test.com",
            ssh_timeout=35,
            refresh_interval=7,
            log_paths=LogPathConfig(
                default_pattern="{work_dir}/output/{job_id}.log",
                specific_projects={"test": "{work_dir}/test/{job_id}.out"},
            ),
        )

        ConfigLoader.save(original, config_file)
        loaded = ConfigLoader.load(config_file)

        assert loaded.remote_host == original.remote_host
        assert loaded.ssh_timeout == original.ssh_timeout
        assert loaded.refresh_interval == original.refresh_interval
        assert loaded.log_paths.default_pattern == original.log_paths.default_pattern
        assert (
            loaded.log_paths.specific_projects == original.log_paths.specific_projects
        )

    def test_get_default_config_path(self):
        """Test getting default config path."""
        path = ConfigLoader.get_default_config_path()

        assert path == Path.home() / ".config" / "slurm_monitor" / "config.json"
        assert isinstance(path, Path)

    def test_load_searches_default_paths(self, tmp_path, monkeypatch):
        """Test that load searches default paths in order."""
        # Create a config in second default location (cwd)
        config_data = {"remote_host": "default.path.com"}
        config_file = tmp_path / "config.json"

        with open(config_file, "w") as f:
            json.dump(config_data, f)

        # Monkeypatch the DEFAULT_CONFIG_PATHS to include our test path
        test_paths = [
            Path("/nonexistent/path/config.json"),
            config_file,
        ]
        monkeypatch.setattr(ConfigLoader, "DEFAULT_CONFIG_PATHS", test_paths)

        config = ConfigLoader.load()

        assert config.remote_host == "default.path.com"

    def test_load_skips_invalid_default_configs(self, tmp_path, monkeypatch):
        """Test that load skips invalid configs in default search."""
        # Create invalid config in cwd
        config_file = tmp_path / "config.json"
        with open(config_file, "w") as f:
            f.write("{ invalid }")

        # Change cwd to tmp_path
        monkeypatch.chdir(tmp_path)

        # Should fall back to defaults instead of raising error
        config = ConfigLoader.load()

        assert config.remote_host == "localhost"  # default value
