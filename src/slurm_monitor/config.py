"""Configuration loader for Slurm Monitor.

Supports TOML (primary) and JSON (backward-compatible) config formats.
Configuration is profile-based: each profile defines a cluster connection
with its own SSH, log, and Slurm settings. Global defaults are merged
into each profile.
"""

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SSHConfig:
    """SSH connection settings for a cluster."""

    host: str = "localhost"
    port: int = 22
    username: str = ""
    key_filename: str = ""
    passphrase: str = ""
    jump_host: str = ""


@dataclass
class LogConfig:
    """Log path resolution settings."""

    default_pattern: str = "{work_dir}/logs/{job_id}.out"
    specific_projects: dict[str, str] = field(default_factory=dict)
    view_command: str = "tail -f {log_path}"


@dataclass
class SlurmConfig:
    """Slurm command format settings."""

    squeue_format: str = "%i|%j|%T|%M|%Z"
    sacct_format: str = "JobID,JobName,State,Elapsed,WorkDir"


@dataclass
class ProfileConfig:
    """Configuration for a single cluster/project profile."""

    name: str = "default"
    ssh: SSHConfig = field(default_factory=SSHConfig)
    log: LogConfig = field(default_factory=LogConfig)
    slurm: SlurmConfig = field(default_factory=SlurmConfig)
    refresh_interval: int = 5
    sacct_refresh_interval: int = 60
    ssh_timeout: int = 10


@dataclass
class AppConfig:
    """Top-level application configuration with multiple profiles."""

    profiles: dict[str, ProfileConfig] = field(default_factory=dict)

    def get_profile(self, name: str) -> ProfileConfig:
        """Get a profile by name.

        Args:
            name: Profile name

        Returns:
            ProfileConfig for the given name

        Raises:
            KeyError: If profile does not exist
        """
        if name not in self.profiles:
            raise KeyError(
                f"Profile '{name}' not found. "
                f"Available profiles: {', '.join(self.profiles.keys()) or '(none)'}"
            )
        return self.profiles[name]

    @property
    def profile_names(self) -> list[str]:
        """Return list of available profile names."""
        return list(self.profiles.keys())


def _merge_ssh(defaults: dict, overrides: dict) -> SSHConfig:
    """Merge SSH config from defaults and overrides."""
    merged = {**defaults, **overrides}
    return SSHConfig(
        host=merged.get("host", "localhost"),
        port=merged.get("port", 22),
        username=merged.get("username", ""),
        key_filename=merged.get("key_filename", ""),
        passphrase=merged.get("passphrase", ""),
        jump_host=merged.get("jump_host", ""),
    )


def _merge_log(defaults: dict, overrides: dict) -> LogConfig:
    """Merge log config from defaults and overrides."""
    merged = {**defaults, **overrides}
    # specific_projects needs deep merge
    projects = {**defaults.get("specific_projects", {})}
    projects.update(overrides.get("specific_projects", {}))
    return LogConfig(
        default_pattern=merged.get(
            "default_pattern", "{work_dir}/logs/{job_id}.out"
        ),
        specific_projects=projects,
        view_command=merged.get("view_command", "tail -f {log_path}"),
    )


def _merge_slurm(defaults: dict, overrides: dict) -> SlurmConfig:
    """Merge Slurm config from defaults and overrides."""
    merged = {**defaults, **overrides}
    return SlurmConfig(
        squeue_format=merged.get("squeue_format", "%i|%j|%T|%M|%Z"),
        sacct_format=merged.get(
            "sacct_format", "JobID,JobName,State,Elapsed,WorkDir"
        ),
    )


def _parse_profile(
    name: str, profile_data: dict, defaults: dict
) -> ProfileConfig:
    """Parse a single profile, merging with defaults."""
    return ProfileConfig(
        name=name,
        ssh=_merge_ssh(
            defaults.get("ssh", {}), profile_data.get("ssh", {})
        ),
        log=_merge_log(
            defaults.get("log", {}), profile_data.get("log", {})
        ),
        slurm=_merge_slurm(
            defaults.get("slurm", {}), profile_data.get("slurm", {})
        ),
        refresh_interval=profile_data.get(
            "refresh_interval", defaults.get("refresh_interval", 5)
        ),
        sacct_refresh_interval=profile_data.get(
            "sacct_refresh_interval",
            defaults.get("sacct_refresh_interval", 60),
        ),
        ssh_timeout=profile_data.get(
            "ssh_timeout", defaults.get("ssh_timeout", 10)
        ),
    )


def _from_toml_dict(data: dict) -> AppConfig:
    """Build AppConfig from parsed TOML dictionary."""
    defaults = data.get("defaults", {})
    profiles_data = data.get("profiles", {})

    if not profiles_data:
        # No profiles defined: create a single "default" profile from defaults
        host = defaults.get("ssh", {}).get("host", "localhost")
        default_profile_data = {"ssh": {"host": host}}
        profiles = {
            "default": _parse_profile("default", default_profile_data, defaults)
        }
    else:
        profiles = {}
        for name, profile_data in profiles_data.items():
            # Host must be set at profile level (required per-profile)
            if "host" not in profile_data and "host" not in profile_data.get(
                "ssh", {}
            ):
                ssh_defaults = defaults.get("ssh", {})
                if "host" not in ssh_defaults:
                    raise ValueError(
                        f"Profile '{name}' is missing required 'host' field"
                    )
            # Move top-level 'host' into ssh section for convenience
            if "host" in profile_data:
                ssh = profile_data.get("ssh", {})
                ssh["host"] = profile_data.pop("host")
                profile_data["ssh"] = ssh
            profiles[name] = _parse_profile(name, profile_data, defaults)

    return AppConfig(profiles=profiles)


def _from_legacy_json(data: dict) -> AppConfig:
    """Build AppConfig from legacy flat JSON config (backward compatibility).

    Converts the old format:
        {"remote_host": "...", "ssh_timeout": 10, "refresh_interval": 2,
         "log_paths": {"default_pattern": "...", "specific_projects": {...}}}

    Into the new profile-based format with a single "default" profile.
    """
    log_paths = data.get("log_paths", {})
    profile = ProfileConfig(
        name="default",
        ssh=SSHConfig(host=data.get("remote_host", "localhost")),
        log=LogConfig(
            default_pattern=log_paths.get(
                "default_pattern", "{work_dir}/logs/{job_id}.out"
            ),
            specific_projects=log_paths.get("specific_projects", {}),
        ),
        slurm=SlurmConfig(),
        refresh_interval=data.get("refresh_interval", 5),
        ssh_timeout=data.get("ssh_timeout", 10),
    )
    return AppConfig(profiles={"default": profile})


class ConfigLoader:
    """Loader for application configuration."""

    DEFAULT_CONFIG_PATHS = [
        Path.home() / ".config" / "slurm_monitor" / "config.toml",
        Path.home() / ".config" / "slurm_monitor" / "config.json",
        Path.cwd() / "config.toml",
        Path.cwd() / "config.json",
    ]

    @staticmethod
    def locate(
        config_path: Optional[Path] = None,
    ) -> tuple[Path, bool]:
        """Locate the config file the loader will use.

        Returns ``(path, found)``. If ``config_path`` is given, the path is
        returned verbatim with ``found = config_path.exists()``. Otherwise
        walks :attr:`DEFAULT_CONFIG_PATHS` and returns the first match, or
        the canonical default path with ``found = False``.
        """
        if config_path is not None:
            return config_path, config_path.exists()
        for path in ConfigLoader.DEFAULT_CONFIG_PATHS:
            if path.exists():
                return path, True
        return ConfigLoader.DEFAULT_CONFIG_PATHS[0], False

    @staticmethod
    def load(config_path: Optional[Path] = None) -> AppConfig:
        """Load configuration from file or use defaults.

        Args:
            config_path: Optional path to config file. If None, searches
                        default locations.

        Returns:
            AppConfig instance with loaded or default values

        Raises:
            ValueError: If specified config file is invalid
            FileNotFoundError: If explicit config_path doesn't exist
        """
        if config_path is not None:
            return ConfigLoader._load_from_file(config_path)

        for path in ConfigLoader.DEFAULT_CONFIG_PATHS:
            if path.exists():
                try:
                    return ConfigLoader._load_from_file(path)
                except (ValueError, tomllib.TOMLDecodeError):
                    continue

        # No config file found: single default profile
        return AppConfig(
            profiles={"default": ProfileConfig(name="default")}
        )

    @staticmethod
    def _load_from_file(path: Path) -> AppConfig:
        """Load configuration from a specific file.

        Args:
            path: Path to config file

        Returns:
            AppConfig instance

        Raises:
            ValueError: If file is invalid
            FileNotFoundError: If file doesn't exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        suffix = path.suffix.lower()

        if suffix == ".toml":
            return ConfigLoader._load_toml(path)
        elif suffix == ".json":
            return ConfigLoader._load_json(path)
        else:
            raise ValueError(
                f"Unsupported config format: {suffix}. Use .toml or .json"
            )

    @staticmethod
    def _load_toml(path: Path) -> AppConfig:
        """Load TOML config file."""
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"Invalid TOML in config file {path}: {e}") from e
        return _from_toml_dict(data)

    @staticmethod
    def _load_json(path: Path) -> AppConfig:
        """Load JSON config file (legacy backward compatibility)."""
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON in config file {path}: {e}"
            ) from e
        return _from_legacy_json(data)

    @staticmethod
    def save_toml(config: AppConfig, path: Path) -> None:
        """Save configuration as TOML.

        Args:
            config: AppConfig instance to save
            path: Path where to save the config
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        # We need to pick a profile to extract defaults from.
        # Use the first profile as reference for defaults section.
        first_profile = next(iter(config.profiles.values()), ProfileConfig())

        lines.append("[defaults]")
        lines.append(f"ssh_timeout = {first_profile.ssh_timeout}")
        lines.append(f"refresh_interval = {first_profile.refresh_interval}")
        lines.append(
            f"sacct_refresh_interval = {first_profile.sacct_refresh_interval}"
        )
        lines.append("")

        for name, profile in config.profiles.items():
            lines.append(f"[profiles.{name}]")
            lines.append(f'host = "{profile.ssh.host}"')
            if profile.ssh.username:
                lines.append(f'ssh.username = "{profile.ssh.username}"')
            if profile.ssh.port != 22:
                lines.append(f"ssh.port = {profile.ssh.port}")
            if profile.ssh.key_filename:
                lines.append(
                    f'ssh.key_filename = "{profile.ssh.key_filename}"'
                )
            if profile.ssh.jump_host:
                lines.append(f'ssh.jump_host = "{profile.ssh.jump_host}"')
            if profile.log.default_pattern != "{work_dir}/logs/{job_id}.out":
                lines.append(
                    f'log.default_pattern = "{profile.log.default_pattern}"'
                )
            if profile.log.view_command != "tail -f {log_path}":
                lines.append(
                    f'log.view_command = "{profile.log.view_command}"'
                )
            for proj, pattern in profile.log.specific_projects.items():
                lines.append(
                    f'log.specific_projects.{proj} = "{pattern}"'
                )
            lines.append("")

        with open(path, "w") as f:
            f.write("\n".join(lines))

    @staticmethod
    def get_default_config_path() -> Path:
        """Get the default config file path."""
        return ConfigLoader.DEFAULT_CONFIG_PATHS[0]
