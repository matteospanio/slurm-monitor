"""Command-line interface for slurmhub."""

import sys
from pathlib import Path
from typing import Optional

import click

from slurmhub.config import AppConfig, ConfigLoader, ProfileConfig


def run_first_run_wizard(save_path: Path) -> Optional[AppConfig]:
    """Launch the interactive wizard, collect profiles, save to ``save_path``.

    Returns the populated AppConfig (also written to disk) or None if the
    user cancelled before saving any profile.
    """
    from textual.app import App, ComposeResult

    from slurmhub.widgets.first_run_wizard import (
        ConfirmScreen,
        FirstRunWizardScreen,
    )

    collected: dict[str, ProfileConfig] = {}

    class WizardApp(App):
        """Tiny host app for the wizard. Lives just long enough to run the
        single-profile flow, then exits."""

        CSS = ""

        def compose(self) -> ComposeResult:  # noqa: D401 — required by Textual
            return []

        def on_mount(self) -> None:
            self._next_step()

        def _next_step(self) -> None:
            default_name = "default" if not collected else f"cluster{len(collected) + 1}"
            self.push_screen(
                FirstRunWizardScreen(default_name=default_name),
                callback=self._after_wizard,
            )

        def _after_wizard(self, profile: Optional[ProfileConfig]) -> None:
            if profile is None:
                # User cancelled — bail out without writing anything
                self.exit()
                return
            # Avoid clobbering an earlier profile with the same name
            chosen_name = profile.name or "default"
            if chosen_name in collected:
                # Append a numeric suffix to keep the table key unique
                i = 2
                while f"{chosen_name}{i}" in collected:
                    i += 1
                chosen_name = f"{chosen_name}{i}"
                profile.name = chosen_name
            collected[chosen_name] = profile
            self.push_screen(
                ConfirmScreen("Add another cluster profile?"),
                callback=self._after_confirm,
            )

        def _after_confirm(self, again: bool) -> None:
            if again:
                self._next_step()
            else:
                self.exit()

    WizardApp().run()

    if not collected:
        return None

    config = AppConfig(profiles=collected)
    ConfigLoader.save_toml(config, save_path)
    return config


def _launch(
    app_config: AppConfig,
    demo: bool,
    database,
    use_tui: bool,
) -> None:
    """Launch the chosen interface against the given config + database.

    The GUI is the default; ``use_tui`` opts back into the Textual TUI (handy
    for headless/SSH-only sessions). Both share the same data + history layer.
    """
    if use_tui:
        from slurmhub.app import SlurmhubApp

        SlurmhubApp(app_config, demo=demo, database=database).run()
    else:
        from slurmhub.qt.app import run_gui

        run_gui(app_config, demo=demo, database=database)


def _open_history_database(app_config: AppConfig):
    """Open + migrate + prune the history database, degrading to None on error.

    Persistence must never block the app from launching, so any failure here is
    reported and swallowed ("monitoring still works, history is off").
    """
    try:
        from slurmhub.db import open_database

        db = open_database(app_config.database)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully
        click.echo(
            f"Job history disabled (database error): {exc}", err=True
        )
        return None

    retention = app_config.database.retention_days
    if db is not None and retention > 0:
        try:
            from slurmhub.db import Repository
            from slurmhub.db.models import utcnow

            with db.session() as session:
                Repository().prune(session, retention, utcnow())
        except Exception as exc:  # noqa: BLE001 — non-fatal
            click.echo(f"History retention prune failed: {exc}", err=True)

    return db


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
@click.option(
    "--demo",
    is_flag=True,
    default=False,
    help="Launch with built-in fixture data (no SSH connection). "
    "Useful for demos, tutorials, and generating documentation screenshots.",
)
@click.option(
    "--tui",
    "use_tui",
    is_flag=True,
    default=False,
    help="Launch the terminal UI instead of the desktop GUI "
    "(useful over SSH / headless sessions).",
)
@click.option(
    "--gui",
    "force_gui",
    is_flag=True,
    default=False,
    help="Force the desktop GUI (the default). Overrides --tui if both are given.",
)
def main(
    config_path: Optional[Path],
    profile_name: Optional[str],
    host: Optional[str],
    list_profiles: bool,
    demo: bool,
    use_tui: bool,
    force_gui: bool,
) -> None:
    """slurmhub - monitor Slurm jobs (desktop GUI by default, --tui for the terminal UI)."""
    use_tui = use_tui and not force_gui

    # Demo mode: synthesize a single-profile config pointing at the
    # built-in fixture host and skip SSH/wizard entirely.
    if demo:
        from slurmhub.config import ProfileConfig as _ProfileConfig
        from slurmhub.config import SSHConfig
        from slurmhub.demo_data import DEMO_HOST, DEMO_USERNAME

        from slurmhub.db import open_demo_database

        profile = _ProfileConfig(
            name="demo",
            ssh=SSHConfig(host=DEMO_HOST, username=DEMO_USERNAME),
        )
        app_config = AppConfig(profiles={"demo": profile})
        # Throwaway in-memory database, seeded with sample history. Never
        # touches ~/.config.
        database = open_demo_database()
        _launch(app_config, demo=True, database=database, use_tui=use_tui)
        return

    # When the user supplied --host or --config, skip the wizard entirely:
    # they are explicitly telling us how to connect.
    if host:
        from slurmhub.config import ProfileConfig as _ProfileConfig
        from slurmhub.config import SSHConfig

        profile = _ProfileConfig(name="default", ssh=SSHConfig(host=host))
        app_config = AppConfig(profiles={"default": profile})
        profile_name = None
    else:
        located_path, found = ConfigLoader.locate(config_path)
        if not found and config_path is None:
            click.echo(
                "No config found. Launching first-run setup wizard…", err=True
            )
            app_config = run_first_run_wizard(located_path)
            if app_config is None:
                click.echo(
                    f"Setup cancelled. Edit {located_path} manually or "
                    "re-run to retry.",
                    err=True,
                )
                sys.exit(1)
            click.echo(
                f"Saved configuration to {located_path}.", err=True
            )
        else:
            app_config = ConfigLoader.load(config_path)

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

    database = _open_history_database(app_config)
    _launch(app_config, demo=False, database=database, use_tui=use_tui)
