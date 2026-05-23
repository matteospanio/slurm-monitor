# Quickstart

This page walks you from a fresh install to a working dashboard against your own
cluster. If you haven't installed `slurmhub` yet, see
[Installation](installation.md) first.

## Launch the app

```bash
# All configured profiles (default)
slurmhub

# Just one profile
slurmhub --profile dei

# Ad-hoc connection without a config file
slurmhub --host login.cluster.example.org

# List what's configured and exit
slurmhub --list-profiles

# Boot the TUI against built-in fixture data (no SSH)
slurmhub --demo
```

## First-run wizard

If no configuration is found at any of the searched paths (see
[Configuration / Overview](../configuration/overview.md)), the wizard pops up
automatically:

```{image} ../_static/screenshots/07_first_run_wizard.svg
:alt: First-run setup wizard
:width: 100%
```

- **Test connection** runs `echo "success"` over SSH and reports the result.
- **Save and continue** writes the profile to
  `~/.config/slurmhub/config.toml` and asks whether to add another cluster.
- **Cancel** / `Esc` aborts without writing anything.

You can re-trigger the wizard at any time by deleting the config file (or pointing
`--config` at a nonexistent path).

## The main screen

```{image} ../_static/screenshots/01_main_job_table.svg
:alt: Main job table
:width: 100%
```

Top-to-bottom, the regions are:

1. **Header** — application title.
2. **ConnectionStatus** — colored dot (● green = ok, ● yellow = loading, ● red = error,
   ○ disconnected), profile name, host, last refresh timestamp. A yellow ⚠ appears when
   an auxiliary fetch (`sinfo`, queue stats, pending details) failed but the main job
   list still loaded.
3. **ClusterStatus** — cluster-wide running/pending counts plus an inline capacity
   strip (CPU/GPU/memory used vs total, nodes up/down).
4. **JobTable** — your jobs (active + recent history merged).
5. **JobDetail** — one-line summary of the currently selected row (toggle with `D`).
6. **StatusBar** — per-state badges, active filter/sort indicators, hint line.
7. **Footer** — clickable Textual binding hints.

## Where to go next

- [SSH setup](ssh-setup.md) — keys, jump hosts, `~/.ssh/config` aliases.
- [Configuration overview](../configuration/overview.md) — the TOML schema.
- [Job table](../usage/job-table.md) — column meanings, filtering, sorting.
- [Keybindings reference](../reference/keybindings.md) — full cheatsheet.
