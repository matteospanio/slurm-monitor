# Installation

`slurmhub` is published on [PyPI](https://pypi.org/project/slurmhub/), so the install
boils down to a single command from your tool of choice.

## Requirements

| Component | Version |
|-----------|---------|
| Python | ≥ 3.12 |
| OpenSSH client | any recent version |
| Access to a Slurm cluster | with `squeue`, `sacct`, `sinfo`, `scontrol` available |
| Terminal | 256-color, UTF-8; ideally one that supports OSC 52 (iTerm2, WezTerm, kitty, Alacritty, tmux with `set-clipboard on`) |

## Install

`slurmhub` is a stand-alone CLI app, so the cleanest install is one that gives it
its own isolated environment. Pick whichever tool you already have:

::::{tab-set}

:::{tab-item} uvx (recommended)
:sync: uvx

[`uvx`](https://docs.astral.sh/uv/guides/tools/) (from [uv](https://docs.astral.sh/uv/))
runs the app on demand in a throw-away environment — nothing is left on disk between
runs. Perfect for trying it out, or for running on machines where you don't want to
install anything permanently.

```bash
uvx slurmhub --demo            # one-shot run
uvx slurmhub --help
```

To make `slurmhub` available on your `$PATH` permanently:

```bash
uv tool install slurmhub
slurmhub --help
```

```{tip}
If you don't have `uv` yet:

   curl -LsSf https://astral.sh/uv/install.sh | sh
```
:::

:::{tab-item} pipx
:sync: pipx

[`pipx`](https://pipx.pypa.io/) installs Python CLI apps into per-app virtual
environments and exposes the entry point on your `$PATH`:

```bash
pipx install slurmhub
slurmhub --help
```

To upgrade later:

```bash
pipx upgrade slurmhub
```
:::

:::{tab-item} pip
:sync: pip

A plain `pip install` works too, but be careful where you install it. Globally
installing CLI apps with `pip` can mix `slurmhub`'s dependencies into the same
environment as the rest of your Python work and create conflicts.

```bash
# Inside a virtualenv:
pip install slurmhub

# Or per-user (skips sudo, still global-ish):
pip install --user slurmhub
```

```{warning}
On most modern distros, `pip install` outside a venv is blocked by PEP 668. Use
`pipx` or `uv tool install` instead — both are designed exactly for this case.
```
:::

:::{tab-item} From source
:sync: source

For development, or to track `master`:

```bash
git clone https://github.com/matteospanio/slurmhub.git
cd slurmhub
uv sync                  # creates .venv and resolves uv.lock
uv run slurmhub          # run from the checkout
```

`uv sync` installs:

- [textual](https://textual.textualize.io/) — TUI framework
- [rich](https://rich.readthedocs.io/) — terminal rendering
- [paramiko](https://www.paramiko.org/) — SSH client
- [click](https://click.palletsprojects.com/) — CLI parsing

Add `--group dev` for the test suite, `--group docs` to build this site.
:::

::::

## Verifying the installation

```bash
$ slurmhub --help
Usage: slurmhub [OPTIONS]

  slurmhub - TUI application for monitoring Slurm jobs.

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
slurmhub --demo
```

```{seealso}
[Quickstart](quickstart.md) — first-run wizard, main screen layout, where to go next.
```
