# Overview

## File location and format

`slurm-monitor` looks for a configuration file in the following order; the first
existing file wins:

1. `~/.config/slurm_monitor/config.toml` *(preferred — written by the wizard)*
2. `~/.config/slurm_monitor/config.json` *(legacy)*
3. `./config.toml` *(working directory)*
4. `./config.json`

If none of these exists, the [first-run wizard](../getting-started/quickstart.md#first-run-wizard)
launches automatically. You can also pass `--config /path/to/file.toml` to skip the
search.

## Structure

A TOML config has two sections:

- **`[defaults]`** — values applied to every profile, unless overridden
- **`[profiles.<name>]`** — one block per cluster you want to monitor

```toml
[defaults]
ssh_timeout = 10               # seconds per SSH command
refresh_interval = 5           # how often squeue is re-fetched
sacct_refresh_interval = 60    # how often sacct (history) is re-fetched

[defaults.ssh]
# username     = "myuser"
# port         = 22
# key_filename = "~/.ssh/id_rsa"
# passphrase   = ""            # leave empty if using ssh-agent
# jump_host    = ""

[defaults.log]
default_pattern = "{work_dir}/logs/{job_id}.out"
view_command    = "tail -f {log_path}"

[defaults.slurm]
squeue_format = "%i|%j|%T|%M|%Z|%b"
sacct_format  = "JobID,JobName,State,Elapsed,WorkDir"

[profiles.mycluster]
host = "mycluster"            # required — SSH alias or hostname
```

## Field reference

| Field | Section | Type | Default | Meaning |
|-------|---------|------|---------|---------|
| `ssh_timeout` | defaults / profile | int (s) | `10` | Per-command SSH timeout. |
| `refresh_interval` | defaults / profile | int (s) | `5` | How often `squeue` is re-fetched. |
| `sacct_refresh_interval` | defaults / profile | int (s) | `60` | How often `sacct` (history) is re-fetched. |
| `ssh.host` | profile | string | — | Hostname or `~/.ssh/config` alias. **Required.** |
| `ssh.port` | ssh | int | `22` | SSH port. |
| `ssh.username` | ssh | string | (current user) | Login user. |
| `ssh.key_filename` | ssh | string | (default keys) | Path to a specific private key. |
| `ssh.passphrase` | ssh | string | `""` | Key passphrase (prefer using `ssh-agent`). |
| `ssh.jump_host` | ssh | string | `""` | Hostname of an SSH bastion. |
| `log.default_pattern` | log | string | `{work_dir}/logs/{job_id}.out` | Fallback log path if `scontrol` doesn't return one. Supports `{work_dir}`, `{job_id}`, `{project_name}` tokens. |
| `log.specific_projects` | log | table | `{}` | Per-project log path overrides. |
| `log.view_command` | log | string | `tail -f {log_path}` | Command used internally when streaming logs. Supports `{log_path}`. |
| `slurm.squeue_format` | slurm | string | `%i\|%j\|%T\|%M\|%Z\|%b` | `squeue -o` format. |
| `slurm.sacct_format` | slurm | string | `JobID,JobName,State,Elapsed,WorkDir` | `sacct --format` fields. |

## Legacy JSON

The previous flat JSON format is still loaded if no TOML file is present, and
converted to a single `default` profile at runtime:

```json
{
  "remote_host": "cluster.example.edu",
  "ssh_timeout": 10,
  "refresh_interval": 5,
  "log_paths": {
    "default_pattern": "{work_dir}/logs/{job_id}.out",
    "specific_projects": {
      "ml_project": "{work_dir}/ml/logs/{job_id}.log"
    }
  }
}
```

New deployments should use TOML — see [Examples](examples.md).

## Where to go next

- [Profiles](profiles.md) — multi-cluster tabs.
- [Log paths](log-paths.md) — token-based resolution and per-project overrides.
- [Examples](examples.md) — copy-paste configs for common situations.
