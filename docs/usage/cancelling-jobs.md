# Cancelling jobs

`c` on a job row (from the main table or the detail screen) opens a confirmation
modal:

```{image} ../_static/screenshots/09_confirm_scancel.svg
:alt: scancel confirmation modal
:width: 100%
```

- `y` runs `scancel <jobid>` on the cluster.
- `n` / `Esc` aborts without touching SSH.

## Why a confirmation modal

The selected `SlurmJob` is captured at the moment you press `c`. Even if the cursor
moves before you confirm, only the originally selected job is cancelled. This avoids
the classic "I scrolled while the modal was open and cancelled the wrong job" bug.

## Already-terminal jobs

Jobs already in `COMPLETED`, `FAILED`, `CANCELLED`, or `TIMEOUT` state short-circuit
with a warning — no SSH round trip happens.

## What it doesn't do

`slurmhub` runs Slurm's standard `scancel` command — it does not call
`scancel --signal=KILL`, `scancel --batch`, or any of the more aggressive forms. If
you need those, use the shell. The TUI is intentionally conservative here.
