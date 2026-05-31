# Database

slurmhub keeps a durable history of the jobs it observes — metadata, a time-series of
resource usage, log paths, and favourites — in a local SQLite database. This powers the
[Job history & analytics](../usage/job-history.md) screen. The database is managed with
[SQLAlchemy](https://www.sqlalchemy.org/) and migrated with
[Alembic](https://alembic.sqlalchemy.org/), so the schema stays forward-compatible
across releases (migrations run automatically at startup).

## Defaults

Persistence is **on by default**. The first time you run slurmhub it creates and
migrates `~/.config/slurmhub/jobs.db` (alongside `config.toml`), and starts recording.
There is nothing to configure to get started — existing users simply begin collecting
history on upgrade.

```{note}
SQLite runs in WAL mode, so you will also see `jobs.db-wal` and `jobs.db-shm`
sidecar files next to the database. That is expected.
```

## The `[database]` section

All settings are app-level (a single shared database across all profiles):

```toml
[database]
enabled = true              # set false to disable history capture entirely
path = ""                   # override the DB location; empty = ~/.config/slurmhub/jobs.db
retention_days = 0          # 0 = keep everything; N = prune runs older than N days
capture_utilization = true  # also sample measured GPU%/memory for running jobs
utilization_interval = 60   # seconds between utilisation samples
```

| Key | Default | Meaning |
|-----|---------|---------|
| `enabled` | `true` | When `false`, no database is opened and the history screen reports that it's disabled. |
| `path` | *(config dir)* | Absolute path to the SQLite file. Empty uses `~/.config/slurmhub/jobs.db`. |
| `retention_days` | `0` | At startup, runs whose last-seen time is older than this many days are pruned. `0` keeps everything. **Favourites are always exempt.** |
| `capture_utilization` | `true` | When enabled, a slower background pass runs `scontrol`/`sstat`/`nvidia-smi` for running jobs to record measured GPU utilisation and actual memory use. |
| `utilization_interval` | `60` | Seconds between utilisation samples (kept slower than the live refresh so it never delays the job table). |

## What gets captured

- **Every refresh cycle**, each active job's state, elapsed time, and *allocated*
  resources (CPUs, GPUs, requested memory) are recorded as a usage snapshot. Terminal
  jobs (completed/failed/cancelled) are recorded once but not re-snapshotted.
- **On the utilisation cadence** (if enabled), measured GPU% and actual memory are
  added for running jobs — this is the source of the "Avg GPU util" figure.
- **Logs**: only the stdout/stderr *paths* are stored; log content is still streamed
  live over SSH on demand.

```{tip}
Reducing SSH load: set `capture_utilization = false` to skip the extra
`scontrol`/`sstat`/`nvidia-smi` calls. You still get full GPU-/CPU-/memory-hour
aggregates from the allocation data — you just lose the measured-utilisation figure.
```

## Demo mode

`slurmhub --demo` uses a throwaway in-memory database pre-seeded with sample history and
favourites. It never touches `~/.config/slurmhub/jobs.db`, so you can explore the
history and analytics screens (and regenerate screenshots) without affecting your real
data.

## Disabling persistence

```toml
[database]
enabled = false
```

The app runs exactly as before — pressing `H` simply reports that history is disabled.
Your config is otherwise untouched, and this setting is preserved when the config is
saved.
