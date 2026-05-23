# slurmhub

[![Tests](https://github.com/matteospanio/slurmhub/actions/workflows/tests.yml/badge.svg)](https://github.com/matteospanio/slurmhub/actions/workflows/tests.yml)
[![Docs](https://github.com/matteospanio/slurmhub/actions/workflows/docs.yml/badge.svg)](https://matteospanio.github.io/slurmhub/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/license-GPLv3-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)](CHANGELOG.md)
[![Built with Textual](https://img.shields.io/badge/built%20with-Textual-5546ff.svg)](https://textual.textualize.io/)

A keyboard-driven terminal UI for monitoring [Slurm](https://slurm.schedmd.com/) jobs
in real time over SSH. It runs the standard Slurm command-line tools
(`squeue`, `sacct`, `scontrol`, `sinfo`, `sstat`, `nvidia-smi`, `scancel`) against one
or more clusters, parses the output, and presents the result as a rich dashboard
built with [Textual](https://textual.textualize.io/).

![main job table](docs/_static/screenshots/01_main_job_table.svg)

## Features

- **Real-time job table** — active jobs from `squeue` merged with recent history from
  `sacct`, color-coded by state.
- **Per-job detail screen** — `scontrol` stats with time / memory / per-GPU
  utilisation bars; one keystroke to the stdout, stderr, or submitted batch script.
- **Cluster dashboard** — cluster-wide CPU / GPU / memory bars, partition summary,
  per-node table fed by `sinfo`.
- **Multi-cluster tabs** — configure several clusters and switch with `h` / `l`;
  filter, search, and sort state is remembered per tab.
- **Vim-style navigation** throughout.
- **OSC 52 yank** — copy job IDs, paths, and log lines to the system clipboard
  through SSH, no `xclip` / `pbcopy` required.
- **First-run wizard** that writes a working TOML config and tests the SSH
  connection.
- **Demo mode** (`--demo`) — exercise the entire TUI against built-in fixture data,
  no cluster needed.

## Installation

`slurmhub` is built with [uv](https://github.com/astral-sh/uv). It requires
Python ≥ 3.12 and an OpenSSH client.

```bash
# Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install slurmhub as a CLI tool
uv tool install git+https://github.com/matteospanio/slurmhub.git

# Run
slurmhub
```

Or clone and run from source:

```bash
git clone https://github.com/matteospanio/slurmhub.git
cd slurmhub
uv sync
uv run slurmhub
```

Try it without a Slurm cluster:

```bash
slurmhub --demo
```

## Quick start

1. Run `slurmhub`. If no config exists at `~/.config/slurmhub/config.toml`,
   the **first-run wizard** walks you through creating one.
2. Set up passwordless SSH to your cluster — `ssh-copy-id` your key and add a
   `Host` alias in `~/.ssh/config`.
3. Reference the alias in your config:

   ```toml
   [profiles.mycluster]
   host = "mycluster"
   ```

Full SSH and configuration walkthrough:
[docs site → Getting started](https://matteospanio.github.io/slurmhub/getting-started/installation.html).

## Documentation

The full documentation lives at
**[matteospanio.github.io/slurmhub](https://matteospanio.github.io/slurmhub/)**.

- [Getting started](https://matteospanio.github.io/slurmhub/getting-started/installation.html) — installation, quickstart, SSH setup
- [Configuration](https://matteospanio.github.io/slurmhub/configuration/overview.html) — TOML schema, profiles, log paths, worked examples
- [Usage guides](https://matteospanio.github.io/slurmhub/usage/job-table.html) — job table, detail screen, log viewer, cluster dashboard, batch script, scancel
- [Reference](https://matteospanio.github.io/slurmhub/reference/keybindings.html) — keybindings, info sources, troubleshooting
- [Changelog](CHANGELOG.md) — release notes

Sphinx sources are under [`docs/`](docs/). Build locally with:

```bash
uv sync --group docs
uv run sphinx-build -b html docs docs/_build/html
```

## Development

```bash
uv sync --group dev
uv run pytest                       # run the test suite (417 tests)
pre-commit install                  # enable code-quality hooks
uv run python docs/scripts/generate_screenshots.py  # regenerate docs SVGs
```

See [CLAUDE.md](CLAUDE.md) for project context and development notes.

## License

[GPL-3.0](LICENSE) © Matteo Spanio
