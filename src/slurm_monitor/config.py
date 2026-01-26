"""Configuration loader for Slurm Monitor."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class LogPathConfig:
    """Configuration for log path resolution."""

    default_pattern: str = "{work_dir}/logs/{job_id}.out"
    specific_projects: dict[str, str] = field(default_factory=dict)


@dataclass
class Config:
    """Application configuration."""

    remote_host: str = "localhost"
    ssh_timeout: int = 10
    refresh_interval: int = 2
    log_paths: LogPathConfig = field(default_factory=LogPathConfig)

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """
        Create Config from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            Config instance
        """
        log_paths_data = data.get("log_paths", {})
        log_paths = LogPathConfig(
            default_pattern=log_paths_data.get(
                "default_pattern", "{work_dir}/logs/{job_id}.out"
            ),
            specific_projects=log_paths_data.get("specific_projects", {}),
        )

        return cls(
            remote_host=data.get("remote_host", "localhost"),
            ssh_timeout=data.get("ssh_timeout", 10),
            refresh_interval=data.get("refresh_interval", 2),
            log_paths=log_paths,
        )

    def to_dict(self) -> dict:
        """
        Convert Config to dictionary.

        Returns:
            Configuration as dictionary
        """
        return {
            "remote_host": self.remote_host,
            "ssh_timeout": self.ssh_timeout,
            "refresh_interval": self.refresh_interval,
            "log_paths": {
                "default_pattern": self.log_paths.default_pattern,
                "specific_projects": self.log_paths.specific_projects,
            },
        }


class ConfigLoader:
    """Loader for application configuration."""

    DEFAULT_CONFIG_PATHS = [
        Path.home() / ".config" / "slurm_monitor" / "config.json",
        Path.cwd() / "config.json",
    ]

    @staticmethod
    def load(config_path: Optional[Path] = None) -> Config:
        """
        Load configuration from file or use defaults.

        Args:
            config_path: Optional path to config file. If None, searches
                        default locations.

        Returns:
            Config instance with loaded or default values

        Raises:
            ValueError: If specified config file is invalid JSON
        """
        if config_path is not None:
            # User specified a path, load from there
            return ConfigLoader._load_from_file(config_path)

        # Search default locations
        for path in ConfigLoader.DEFAULT_CONFIG_PATHS:
            if path.exists():
                try:
                    return ConfigLoader._load_from_file(path)
                except (json.JSONDecodeError, ValueError):
                    # Skip invalid config files in default search
                    continue

        # No config file found, use defaults
        return Config()

    @staticmethod
    def _load_from_file(path: Path) -> Config:
        """
        Load configuration from a specific file.

        Args:
            path: Path to config file

        Returns:
            Config instance

        Raises:
            ValueError: If file contains invalid JSON
            FileNotFoundError: If file doesn't exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        try:
            with open(path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file {path}: {e}") from e

        return Config.from_dict(data)

    @staticmethod
    def save(config: Config, path: Path) -> None:
        """
        Save configuration to file.

        Args:
            config: Config instance to save
            path: Path where to save the config

        Raises:
            OSError: If file cannot be written
        """
        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(config.to_dict(), f, indent=2)

    @staticmethod
    def get_default_config_path() -> Path:
        """
        Get the default config file path.

        Returns:
            Path to default config location
        """
        return ConfigLoader.DEFAULT_CONFIG_PATHS[0]


if __name__ == "__main__":
    import sys

    # Example usage
    try:
        config = ConfigLoader.load()
        print("Configuration loaded:")
        print(json.dumps(config.to_dict(), indent=2))

        print(f"\nRemote host: {config.remote_host}")
        print(f"SSH timeout: {config.ssh_timeout}s")
        print(f"Refresh interval: {config.refresh_interval}s")
        print(f"Default log pattern: {config.log_paths.default_pattern}")

        if config.log_paths.specific_projects:
            print("\nSpecific project patterns:")
            for project, pattern in config.log_paths.specific_projects.items():
                print(f"  {project}: {pattern}")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
