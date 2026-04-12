"""Command-line interface for Slurm Monitor."""

from pathlib import Path
from typing import Optional

import click

from slurm_monitor.config import AppConfig, ConfigLoader


@click.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to configuration file (.toml or .json).",
)
@click.option(
    "--profile",
    "profile_name",
    type=str,
    default=None,
    help="Run only a specific profile instead of all configured profiles.",
)
@click.option(
    "--host",
    type=str,
    default=None,
    help="Override the SSH host (creates a temporary 'default' profile).",
)
@click.option(
    "--list-profiles",
    is_flag=True,
    default=False,
    help="List available profiles and exit.",
)
def main(
    config_path: Optional[Path],
    profile_name: Optional[str],
    host: Optional[str],
    list_profiles: bool,
) -> None:
    """Slurm Monitor - TUI application for monitoring Slurm jobs."""
    from slurm_monitor.app import SlurmMonitorApp

    app_config = ConfigLoader.load(config_path)

    if host:
        from slurm_monitor.config import ProfileConfig, SSHConfig

        profile = ProfileConfig(
            name="default", ssh=SSHConfig(host=host)
        )
        app_config = AppConfig(profiles={"default": profile})
        profile_name = None  # use all (just the one we created)

    if list_profiles:
        if not app_config.profiles:
            click.echo("No profiles configured.")
        else:
            click.echo("Available profiles:")
            for name, profile in app_config.profiles.items():
                click.echo(f"  {name}: {profile.ssh.host}")
        return

    if profile_name:
        try:
            profile = app_config.get_profile(profile_name)
        except KeyError as e:
            raise click.ClickException(str(e)) from e
        app_config = AppConfig(profiles={profile_name: profile})

    app = SlurmMonitorApp(app_config)
    app.run()
