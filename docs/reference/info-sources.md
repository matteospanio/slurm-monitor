# Information sources

The TUI is a thin presentation layer; **every piece of data on screen comes from a
standard Slurm CLI command**. Knowing the underlying command makes it easy to verify
a value or diagnose a discrepancy directly from the shell.

| TUI element | Underlying command (run over SSH) | Notes |
|-------------|-----------------------------------|-------|
| Job table (active) | `squeue --me -o "%i\|%j\|%T\|%M\|%Z\|%b" --noheader` | Fields: id, name, state, time, work dir, GRES. |
| Job table (history) | `sacct -X --format=JobID,JobName,State,Elapsed,WorkDir --units=M -n` | Active jobs override history if both contain the same ID. |
| Cluster running / pending totals | `squeue --noheader -o "%T"` | Counted by state. Re-fetched every 30 s. |
| Pending reason / priority / QOS / submit time | `squeue --me -t PENDING --noheader -o "%i\|%r\|%Q\|%V\|%q"` | Populated only for PENDING jobs. |
| Queue rank | `squeue -t PENDING --noheader -o "%Q\|%i" --sort=-Q` | 1-based position among **all** pending jobs cluster-wide. |
| Job detail header / timing / log paths | `scontrol show job <jobid>` | Source of `StdOut`, `StdErr`, `Command`, `SubmitTime`, `StartTime`, `EndTime`, `Partition`, `NodeList`, `TimeLimit`, `ReqTRES`. |
| Live memory usage | `sstat --format=MaxRSS -j <jobid>.batch --noheader` | Only fetched for RUNNING jobs. |
| Per-GPU utilization | `srun --jobid=<jobid> --overlap nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits` | Only attempted when `ReqTRES` declares GPUs. |
| Cluster capacity bars | `sinfo -h -N -o "%N\|%R\|%T\|%C\|%e\|%m\|%G\|%E"` | One row per (node, partition). Rows are deduplicated on node name. |
| Partition table | `sinfo -h -o "%R\|%D\|%C\|%G\|%m\|%a"` | Per-state node counts are filled in from the node walk above. |
| Log streaming | `tail -n 50 -f <log_path>` over a paramiko channel | The log path comes from `scontrol`; falls back to the configured pattern. |
| Batch script viewer | `scontrol write batch_script <jobid> -` | Read-only. |
| Cancel a job | `scancel <jobid>` | Triggered by `c`, gated by a confirmation modal. |

If you ever doubt a value in the UI, run the corresponding command in an SSH shell —
that is exactly what the TUI did, parsed, and rendered.
