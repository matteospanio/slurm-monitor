# Job detail

Press `Enter` on a job row to open the detail screen. It runs `scontrol show job <id>`
for static info, `sstat` for live memory usage, and (for GPU jobs)
`srun --jobid=<id> --overlap nvidia-smi …` for per-GPU utilisation.

```{image} ../_static/screenshots/02_job_detail.svg
:alt: Job detail screen
:width: 100%
```

## How to read it

- **Time / Memory bars** are computed as `RunTime / TimeLimit` and
  `MaxRSS / ReqTRES.mem`. Bars over 80 % are red; 50 – 80 % yellow; below 50 % green.
- **GPU utilisation** comes from `nvidia-smi --query-gpu=…` issued via
  `srun --overlap` so the readings come from inside the job's allocation. If your
  cluster restricts `srun --overlap`, the per-GPU bars stay blank — the
  `Allocated: 4x l40s` line still appears from `scontrol`.
- **Log paths** are read directly from `scontrol`'s `StdOut` / `StdErr` fields, so
  they reflect Slurm's actual file path including any `%j` / `%a` expansion already
  resolved.

## Persisted history fallback

Finished jobs may disappear from `scontrol` quickly on some clusters. When that
happens, SlurmHub falls back to the local history database for the detail view
instead of showing an empty/error page.

- Stored run metadata (state, timings, partition, requested CPU/GPU/memory) is shown
  from the `jobs` table.
- Stored `stdout` / `stderr` paths are reused when available, so you can still open
  logs for completed jobs.
- A native interactive Qt chart (pyqtgraph) is rendered from persisted snapshots
  (`usage_snapshots`): GPU utilisation (%) and measured CPU utilisation (%) across
  captured samples, with allocated-CPU context shown on a secondary axis.
- Detail metadata below the chart is presented in a structured two-column table
  inside a card, instead of an unstructured text block.
- A terminal-state snapshot is stored once per run, so completed runs keep at least
  one persisted usage point for post-mortem inspection.

## Keybindings

| Key | Action |
|-----|--------|
| `o` | Open the [log viewer](log-viewer.md) on `StdOut`. |
| `e` | Open the [log viewer](log-viewer.md) on `StdErr`. |
| `v` | Open the [batch script viewer](batch-script.md) (the submitted `sbatch` script). |
| `c` | `scancel` this job — see [Cancelling jobs](cancelling-jobs.md). |
| `y` | Copy a value to the clipboard. Cycles: job ID → stdout path → stderr path → work dir. |
| `j` / `k` / `g` / `G` | Scroll within the detail body. |
| `Esc` / `q` | Back to the job list. |
