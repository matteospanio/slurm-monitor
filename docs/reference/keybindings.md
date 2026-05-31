# Keybindings reference

```{image} ../_static/screenshots/06_help_screen.svg
:alt: Help screen modal
:width: 100%
```

Press `?` on any screen for a context-specific cheatsheet inside the app. This page
is the union of all of them.

## Main job table

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Refresh now (also forces a sacct re-fetch) |
| `?` | Help |
| `j` / `k` | Cursor down / up |
| `g` / `G` | First / last row |
| `h` / `l` | Previous / next profile tab |
| `Enter` | Open the **Job Detail** screen |
| `d` | Open the **Cluster Dashboard** |
| `H` (Shift+H) | Open the **Job History & analytics** screen |
| `D` (Shift+D) | Toggle the bottom detail panel |
| `/` | Open the search bar (`Esc` clears, `Enter` confirms) |
| `1` / `2` / `3` / `4` | Toggle filter RUNNING / PENDING / COMPLETED / FAILED |
| `0` | Clear state filter (show all) |
| `s` | Cycle sort mode (id → time → name → state) |
| `y` | Yank the selected job ID to the system clipboard (OSC 52) |
| `c` | `scancel` the selected job (confirmation modal) |
| `Esc` | Close search bar / pop the current screen |

## Job detail screen

| Key | Action |
|-----|--------|
| `o` | Open the log viewer on `StdOut` |
| `e` | Open the log viewer on `StdErr` |
| `v` | Open the batch script viewer |
| `c` | `scancel` this job |
| `f` | Toggle this run as a favourite |
| `n` | Edit the favourite's note |
| `y` | Cycle yank: job ID → stdout path → stderr path → work dir |
| `j` / `k` / `g` / `G` | Scroll within the detail body |
| `Esc` / `q` | Back to the job list |

## Job history screen

| Key | Action |
|-----|--------|
| `a` | Toggle past-runs / usage-aggregates view |
| `f` | Toggle the selected run as a favourite |
| `n` | Edit the selected run's note |
| `p` | Toggle current-profile / all-profiles scope |
| `t` | Cycle the date range (all / 24h / 7d / 30d) |
| `F` (Shift+F) | Show favourites only |
| `1` / `2` / `3` / `4` | Filter RUNNING / PENDING / COMPLETED / FAILED |
| `0` | Clear the state filter |
| `/` | Search by job name or ID |
| `Enter` | Open the selected run's detail screen |
| `r` | Re-run the query |
| `j` / `k` / `g` / `G` | Move the cursor |
| `Esc` / `q` | Back to the job list |

## Log viewer

| Key | Action |
|-----|--------|
| `f` | Toggle FOLLOW / PAUSED |
| `/` | Open the search bar |
| `n` / `N` | Jump to next / previous match |
| `w` | Save the buffer to `~/Downloads/<jobid>_<stream>.log` |
| `y` | Copy the current line / match to the clipboard |
| `j` / `k` / `g` / `G` | Scroll |
| `Esc` / `q` | Close the viewer |

## Cluster dashboard

| Key | Action |
|-----|--------|
| `r` | Force-refresh `sinfo` now |
| `j` / `k` / `g` / `G` | Scroll the body |
| `?` | Help cheatsheet |
| `Esc` / `q` | Back to the job list |

## Batch script viewer

| Key | Action |
|-----|--------|
| `w` | Save to `~/Downloads/<jobid>_batch.sh` |
| `y` | Copy the saved path to the clipboard |
| `j` / `k` / `g` / `G` | Scroll |
| `Esc` / `q` | Back |
