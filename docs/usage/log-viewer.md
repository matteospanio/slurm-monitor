# Log viewer

```{image} ../_static/screenshots/03_log_viewer.svg
:alt: Log viewer
:width: 100%
```

The viewer opens a persistent paramiko channel and runs `tail -n 50 -f <log_path>`
on the remote host. Lines are streamed into a `RichLog` widget in chunks.

```{note}
The in-memory buffer is capped at **20 000 lines** to keep memory bounded on
long-running jobs — older lines are evicted as new ones arrive. Search and yank
operate on what's in the buffer; lines that have already been evicted won't match.
```

The header bar reflects the current mode:

- **FOLLOW** — auto-scrolls to keep the bottom in view.
- **PAUSED** — manual scrolling; new lines still arrive but the cursor stays put.

## Search

Press `/` to open the search bar:

```{image} ../_static/screenshots/04_log_viewer_search.svg
:alt: Log viewer with search bar open
:width: 100%
```

Matching is case-insensitive substring against the in-memory buffer. The bar shows a
running match count. Use `n` / `N` to jump between matches; jumping a match pauses
auto-follow so the screen doesn't immediately scroll away.

## Save & yank

| Key | Action |
|-----|--------|
| `w` | Save the buffer to `~/Downloads/<jobid>_<stream>.log` (falls back to `$HOME` if Downloads is missing). |
| `y` | Copy the current match (or the most recent line) to the clipboard via OSC 52 (see [Job table](job-table.md)). |

## All keybindings

| Key | Action |
|-----|--------|
| `f` | Toggle FOLLOW / PAUSED. |
| `/` | Open the search bar. |
| `n` / `N` | Jump to next / previous match. |
| `w` | Save the buffer to disk. |
| `y` | Copy the current line to the clipboard. |
| `j` / `k` / `g` / `G` | Scroll. |
| `Esc` / `q` | Close the viewer (also closes the SSH channel). |
