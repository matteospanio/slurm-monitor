# Batch script viewer

From the detail screen, press `v` to load the `sbatch` script Slurm captured at
submission time. Internally this runs:

```bash
scontrol write batch_script <jobid> -
```

The result is rendered read-only in a `RichLog`.

```{image} ../_static/screenshots/08_batch_script.svg
:alt: Batch script viewer
:width: 100%
```

## Keybindings

| Key | Action |
|-----|--------|
| `w` | Save a copy to `~/Downloads/<jobid>_batch.sh`. |
| `y` | Copy the saved path to the clipboard via OSC 52. |
| `j` / `k` / `g` / `G` | Scroll. |
| `Esc` / `q` | Back. |
