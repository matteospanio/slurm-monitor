# slurmhub

A keyboard-driven terminal UI for monitoring [Slurm](https://slurm.schedmd.com/) jobs in
real time over SSH. It runs the standard Slurm command-line tools (`squeue`, `sacct`,
`scontrol`, `sinfo`, `sstat`, `nvidia-smi`, `scancel`) against one or more clusters,
parses the output, and presents the result as a rich dashboard built with
[Textual](https://textual.textualize.io/).

```{image} _static/screenshots/01_main_job_table.svg
:alt: slurmhub main job table
:width: 100%
```

## What can it do?

::::{grid} 2
:::{grid-item-card} Live job table
Active and historical jobs from `squeue` and `sacct`, color-coded by state, with
elapsed time, GPU allocation, pending reasons, and your queue rank cluster-wide.
:::
:::{grid-item-card} Per-job detail
`scontrol`-driven detail screen with time / memory / per-GPU utilisation bars and
direct shortcuts to the job's stdout, stderr, and submitted batch script.
:::
:::{grid-item-card} Cluster dashboard
Cluster-wide capacity bars (CPU, GPU, memory), partition summary, and per-node
table fed by `sinfo`.
:::
:::{grid-item-card} Multi-cluster tabs
Configure several clusters in `~/.config/slurmhub/config.toml` and switch
between them with `h` / `l`. Filter, search and sort state is remembered per tab.
:::
:::{grid-item-card} Job history & analytics
A local SQLite database records every run, its resource usage over time, and your
favourites — browse it with `H`, including GPU/CPU/memory-hour aggregates.
:::
::::

## Quick start

```bash
# Install
uv tool install slurmhub      # or: pipx install slurmhub

# Try it without an SSH connection — the --demo flag uses built-in fixture data
slurmhub --demo

# Run against your cluster
slurmhub --host my-cluster
```

```{tip}
No config? No problem — on first launch `slurmhub` opens an interactive wizard that
collects the SSH details and writes `~/.config/slurmhub/config.toml` for you.
```

## Documentation map

```{toctree}
:maxdepth: 2
:caption: Getting started

getting-started/installation
getting-started/download
getting-started/quickstart
getting-started/ssh-setup
```

```{toctree}
:maxdepth: 2
:caption: Configuration

configuration/overview
configuration/profiles
configuration/log-paths
configuration/database
configuration/examples
```

```{toctree}
:maxdepth: 2
:caption: Usage

usage/job-table
usage/job-detail
usage/log-viewer
usage/cluster-dashboard
usage/job-history
usage/batch-script
usage/cancelling-jobs
```

```{toctree}
:maxdepth: 2
:caption: Reference

reference/keybindings
reference/info-sources
reference/troubleshooting
```

```{toctree}
:maxdepth: 1
:caption: About

about/changelog
```
