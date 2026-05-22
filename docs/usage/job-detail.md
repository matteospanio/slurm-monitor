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
