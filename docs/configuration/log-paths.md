# Log path resolution

The log viewer opens whatever path Slurm's `scontrol show job` reports for `StdOut`
and `StdErr` — that is the authoritative source. The configuration here is a
**fallback** for cases where `scontrol` does not return a path (rare, very old jobs)
or where the path needs to be reconstructed from job metadata.

## Tokens

| Token | Meaning |
|-------|---------|
| `{job_id}` | Slurm job ID (e.g. `421578`). |
| `{work_dir}` | The job's working directory as reported by `squeue` / `scontrol`. |
| `{project_name}` | Auto-detected from `work_dir` (the directory whose name matches one of the keys under `log.specific_projects`). |

## Default pattern

```toml
[profiles.mycluster]
host = "mycluster"
log.default_pattern = "{work_dir}/logs/{job_id}.out"
```

If `scontrol` doesn't return a path, the viewer interpolates the pattern with the
job's `work_dir` and `job_id`.

## Per-project overrides

When jobs in different directory trees write logs in different conventions, declare
per-project patterns:

```toml
[profiles.mycluster]
host = "mycluster"
log.default_pattern = "{work_dir}/logs/{job_id}.out"
log.specific_projects.ml_training   = "{work_dir}/experiments/{job_id}.log"
log.specific_projects.simulations   = "{work_dir}/sim_output/job_{job_id}/stdout.txt"
log.specific_projects.preprocessing = "{work_dir}/data/logs/{job_id}.out"
```

The first key whose name appears as a *substring* of the job's `work_dir` wins;
otherwise `default_pattern` is used. Use specific names (e.g. `ml_training_2026`
rather than `ml`) when several project names share a common substring.

## The view command

`log.view_command` controls the command run on the remote host when streaming logs.
It defaults to:

```toml
log.view_command = "tail -f {log_path}"
```

You can substitute `less +F`, `bat --paging=never --follow`, or any other follower.
Both the desktop GUI and the TUI honour `log.view_command`.

When left at the default template (`tail -f {log_path}`), both interfaces still
stream with `tail -n 50 -f` for convenience. Neither UI currently exposes a
tail-length control directly in the interface; set a custom `log.view_command`
if you need a different follower behaviour.
