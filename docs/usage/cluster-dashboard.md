# Cluster dashboard

Press `d` from the main screen for a cluster-wide overview, refreshed every 60 s from
two `sinfo` calls.

```{image} ../_static/screenshots/05_cluster_dashboard.svg
:alt: Cluster dashboard
:width: 100%
```

## How to interpret each row

- **Capacity** — sum across all nodes. CPU and memory percentages are computed from
  the per-node `%C` (`Allocated/Idle/Other/Total`) and `RealMemory - FreeMem` fields.
- **Partition table** columns:
  - *Nodes (i/m/a/d)* — counts by state (idle / mixed / allocated / down|drain|fail).
  - *CPUs (free/total)* — `total - alloc` per partition.
  - *GPUs (used/total)* — counted from the partition's `Gres` field plus per-node
    usage.
  - *Mem* — the largest `RealMemory` value seen for the partition, so heterogeneous
    partitions still show a meaningful number rather than double-counting.
  - *Up* — derived from `sinfo`'s `%a` Availability flag.
- **Node table** — the per-node rollup, color-coded by state.

```{note}
GPU *usage* is approximate: allocated / mixed nodes count as "all GPUs used" because
`sinfo` does not expose per-job GPU counts. For exact per-job GPU utilisation, open
the [Job detail screen](job-detail.md) — it queries `nvidia-smi` inside the job's
allocation.
```

## Keybindings

| Key | Action |
|-----|--------|
| `r` | Force-refresh `sinfo` now. |
| `j` / `k` / `g` / `G` | Scroll the body. |
| `?` | Help cheatsheet. |
| `Esc` / `q` | Back to the job list. |
