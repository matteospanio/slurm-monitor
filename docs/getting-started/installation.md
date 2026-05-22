# Installation

## Requirements

| Component | Version |
|-----------|---------|
| Python | ≥ 3.12 |
| OpenSSH client | any recent version |
| Access to a Slurm cluster | with `squeue`, `sacct`, `sinfo`, `scontrol` available |
| Terminal | 256-color, UTF-8; ideally one that supports OSC 52 (iTerm2, WezTerm, kitty, Alacritty, tmux with `set-clipboard on`) |

## Installing with `uv` (recommended)

[`uv`](https://github.com/astral-sh/uv) is the dependency manager used by this project.
It bootstraps Python, creates the virtual environment, and installs the project in a
single step.

```bash
# 1. Install uv itself (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone the repo
git clone https://github.com/matteospanio/slurm-monitor.git
cd slurm-monitor

# 3. Install dependencies (creates .venv from uv.lock)
uv sync

# 4. Run the app
uv run slurm-monitor
```

`uv sync` reads `pyproject.toml` and pins from `uv.lock`. It installs:

- [textual](https://textual.textualize.io/) — TUI framework
- [rich](https://rich.readthedocs.io/) — terminal rendering
- [paramiko](https://www.paramiko.org/) — SSH client
- [click](https://click.palletsprojects.com/) — CLI parsing

## Installing globally

If you would rather expose the `slurm-monitor` command on your `$PATH` without going
through `uv run`:

```bash
uv tool install .
slurm-monitor --help
```

## Verifying the installation

```bash
$ slurm-monitor --help
Usage: slurm-monitor [OPTIONS]

  Slurm Monitor - TUI application for monitoring Slurm jobs.

Options:
  --config PATH        Path to configuration file (.toml or .json).
  --profile TEXT       Run only a specific profile instead of all configured profiles.
  --host TEXT          Override the SSH host (creates a temporary 'default' profile).
  --list-profiles      List available profiles and exit.
  --demo               Launch with built-in fixture data (no SSH connection).
  --help               Show this message and exit.
```

## Try it without a cluster

`--demo` mode boots the entire TUI against a built-in fixture dataset, so you can
explore the interface before configuring SSH:

```bash
slurm-monitor --demo
```

See [Quickstart](quickstart.md) for the next step.
