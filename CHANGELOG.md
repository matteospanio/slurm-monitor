# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> The *Unreleased* section is for changes that are not yet released, but are going to be released in the next version.

## [1.2.0] - Unreleased

### Added

- **PySide6 desktop GUI** — a new dashboard interface, now the default `slurmhub`
  command. It has a left sidebar for navigation, a cluster-profile switcher, a
  header connection strip, a hand-rolled light/dark theme that follows the OS colour
  scheme, and a link to the online documentation. The existing terminal UI stays
  available via `slurmhub --tui`.
- New `slurmhub.qt` package holding the entire Qt view layer (`controller`, `theme`,
  `workers`, `main_window`, `app`). The SSH, parser, history-database, and config
  layers are reused unchanged — blocking calls run on a `QThreadPool` and periodic
  refresh is driven by per-profile `QTimer`s, mirroring the TUI's worker model.
- **Queue / My Jobs screen** — a sortable table of the active profile's merged
  active+historical jobs (colour-coded state badges, CPU/GPU/memory columns), with a
  state filter, a name/ID search, click-to-sort columns, a live cluster summary
  strip, a collapsible detail panel, and `scancel` (behind a confirmation, `Delete`
  shortcut).
- **Cluster Status screen** — CPU/GPU/memory utilisation bars (green/yellow/red by
  threshold), a node-state summary, and partition + node tables, all fed by
  `fetch_sinfo` and refreshed on the cluster cadence.
- **Settings screen** — a GUI proxy for the on-disk config: add/edit/remove cluster
  profiles (SSH, log, slurm, intervals), database options (history on/off, path,
  retention, utilisation capture) with a "Clean up history now" button, and an
  appearance tab (Light/Dark/Auto theme applied live, minimise-to-tray and
  notification toggles). Saves via `ConfigLoader.save_toml`.
- **Qt first-run setup wizard** — shown on first GUI launch when no config exists,
  with an SSH connection test; `--tui` keeps the Textual wizard. A password/passphrase
  prompt now also appears in the GUI when SSH auth is required.
- **History & analytics screen** — a filterable table of persisted runs (date range,
  profile, state, favourites-only, search) with star/unstar and note editing, plus a
  Usage tab showing GPU/CPU/memory-hour totals, average measured GPU utilisation, and
  a per-profile resource-hours bar chart (QtCharts). Reads run on worker threads via
  `Repository.query_runs` / `aggregate_usage`.
- `pytest-qt` (dev) and a headless `tests/qt/` suite (`QT_QPA_PLATFORM=offscreen`).

### Changed

- `slurmhub` now launches the desktop GUI by default; pass `--tui` for the terminal
  UI (handy over SSH) or `--gui` to force the GUI. `--demo` works for both.

## [1.1.0] - 2026-05-31

### Added

- **Persistent job history database** — a local SQLite database (default
  `~/.config/slurmhub/jobs.db`, configurable) records every observed run, a
  time-series of its resource usage, and log paths. Managed with SQLAlchemy and
  migrated with Alembic at startup, so the schema stays forward-compatible. On by
  default; disable with `[database] enabled = false`.
- **Job history & analytics screen** (`H`) — a filterable/searchable table of past
  runs (by state, date range, favourite, current-profile vs all-profiles), plus a
  usage-aggregates view (`a`) showing GPU-hours, CPU-hours, memory GB·h, and average
  measured GPU utilisation, with a per-profile breakdown.
- **Favourites & notes** — star runs (`f`) and annotate them (`n`) from the job
  detail and history screens; favourites are exempt from retention pruning.
- **Configurable retention** — `[database] retention_days` prunes runs older than N
  days at startup (favourites always kept); `0` keeps everything.
- **Measured-utilisation capture** — an optional slower-cadence pass records live
  GPU% / actual memory for running jobs (`[database] capture_utilization`,
  `utilization_interval`).
- New `db/` subpackage (`models`, `engine`, `repository`, Alembic env + initial
  migration, demo seed) and `widgets/history_screen.py`, `widgets/note_input_screen.py`.
- 58 new tests covering the DB models/repository, migrations, retention, threaded
  read/write, aggregates, the capture hook, the history and note-input screens, demo
  isolation, and `[database]` config parsing (475 total).

### Changed

- `squeue` capture now also requests submit time, allocated CPUs, and requested
  memory (`%V|%C|%m`); `sacct` switched to pipe-delimited `--parsable2` with
  `Submit,NCPUS,ReqMem` (also fixes parsing of names/work dirs containing spaces).
  These power stable per-run identity and the CPU/memory-hour aggregates; the live
  views are unchanged.
- `--demo` now ships a seeded in-memory history database so the history and analytics
  screens are demonstrable; it never touches `~/.config`.
- `sqlalchemy>=2.0` and `alembic>=1.13` added as runtime dependencies.

## [1.0.0] - 2026-05-22

First official public release.

### Documentation

- **Sphinx documentation site** under `docs/` (MyST Markdown source), organised into
  *Getting started*, *Configuration*, *Usage*, and *Reference* guides. Built and
  published to GitHub Pages on every push to `master` by `.github/workflows/docs.yml`.
- **Screenshots generated from the real TUI** via `App.save_screenshot()` (SVG),
  driven by a new `--demo` CLI flag that injects fixture data and avoids the need
  for an SSH connection.
- Existing flat `docs/user-guide.md` and `docs/configuration-examples.md` content
  migrated into the structured guide tree.
- Internal development roadmap `plan.md` removed; release notes live in this file
  going forward.

### Added

- `--demo` CLI flag (`slurmhub --demo`) that launches the app against a
  built-in fixture dataset — useful for demos, tutorials, and generating
  documentation screenshots without a live Slurm cluster.
- `slurmhub.demo_data` module with hand-crafted fixture outputs for `squeue`,
  `sacct`, `scontrol`, `sinfo`, `sstat`, and `tail` of log files.
- `DemoSSHClient` (in `slurmhub.ssh_wrapper`) which implements the
  `SSHClient` interface against fixture data.
- `SSHClient.stream_command()` method extracted from the log viewer so streaming
  commands can be intercepted cleanly by `DemoSSHClient` and by future tests.

### Added — Epic 16: UI review pass

- **Persistent help screen** (`?`): a `ModalScreen` lists the keybindings grouped by section for the current context (main, detail, dashboard, log). Replaces the old 10-second notify-toast.
- **Cluster capacity strip on the main screen**: the existing `ClusterStatus` line now also renders `240/512 CPU · 12/16 GPU · 1.4T/2T mem · 18 up · 1 down` when `sinfo` data is available, so cluster-wide health is visible without opening the dashboard.
- **GPU column in the job table** (between Time and Reason). Reuses `SlurmJob.gpu_display`.
- **Per-tab filter / search / sort isolation**: state filter, name search, and sort mode are now stored on `ProfileTab`. Switching tabs preserves each profile's view independently; the search input is re-seeded on tab switch.
- **`D` (Shift+D)**: toggle the bottom job-detail panel.
- **`y` to yank**: copies the selected job ID (main screen) or cycles through job ID → stdout path → stderr path → work dir (detail screen) to the system clipboard via OSC 52 (works over SSH on iTerm2, WezTerm, kitty, Alacritty, tmux with `set-clipboard on`).
- **`c` to scancel** the selected job, guarded by a `ConfirmScreen` modal (Y/N). Works on the main screen and inside the detail screen. The captured `SlurmJob` is closed over so a cursor movement between confirm and execution can't target the wrong job.
- **`v` to view the submitted batch script**: new `BatchScriptScreen` runs `scontrol write batch_script <jobid> -` and renders it read-only. Supports `w` save-to-disk and `y` copy-path-to-clipboard.
- **In-log search**: `/` opens a search bar in `LogScreen`; `n` / `N` jump between case-insensitive matches.
- **`w` save log buffer to disk** (default `~/Downloads/<jobid>_<stream>.log`).
- **`y` copy log line** (current match or most-recent line) to clipboard via OSC 52.
- **Partial-fetch warning surfacing**: when `sinfo`, `queue_stats`, or `pending_details` sub-fetches fail but the main job fetch still succeeds, the failure is recorded in `FetchResult.partial_errors`, shown as a yellow `⚠` next to the `ConnectionStatus` dot, and surfaced via `self.notify(...)` (throttled to once every 5 minutes per profile).
- **Smarter status bar**: shows visible vs total counts (`5 of 18 shown`) when a filter is active; sort mode is rendered as a word (`Sort: time`) instead of a glyph; "/ search · ? help" hint when no filter is active.
- **Resizable JobDetail panel**: CSS switched from `height: 3` to `height: auto; min-height: 2; max-height: 6` so PENDING job rows with reason/rank/QOS/priority/submit_time no longer overflow.
- **`ConfirmScreen` widget** (`widgets/confirm_screen.py`), **`HelpScreen` widget** (`widgets/help_screen.py`), **`BatchScriptScreen` widget** (`widgets/batch_script_screen.py`), shared **OSC 52 clipboard helper** (`widgets/_clipboard.py`), and shared **path helpers** (`widgets/_utils.py`).
- 52 new tests covering the above (404 total).

### Added

- **Cluster dashboard screen** (`d` key). Full-screen view with cluster-wide CPU/GPU/memory bars, a partition summary table (nodes idle/mixed/alloc/down, CPUs free/total, GPUs used/total, memory total, up/down state), and a scrollable per-node table (state, CPU allocation, free/total memory, GPU usage, reason). Refreshes via `sinfo` every 60 s in the background and on demand with `r`. Supports `j`/`k`/`g`/`G` for scrolling and `Esc`/`q` to return.
- **First-run setup wizard**. When no config file exists under the default search path, an interactive `ModalScreen` collects profile name, SSH host, username, port, key path, and log pattern, optionally tests the connection via `SSHClient.check_connection`, and writes `~/.config/slurmhub/config.toml` via `ConfigLoader.save_toml`. Includes an "Add another cluster?" confirmation so multiple profiles can be set up in one session. Passing `--config` or `--host` skips the wizard.
- `ConfigLoader.locate()` — returns `(path, found)` for the resolved config path without touching the silent default-profile fallback. Lets the CLI decide whether to launch the wizard.
- `sinfo_parser` module with `PartitionStats`, `NodeStats`, `ClusterCapacity` dataclasses and a `fetch_sinfo(client)` helper that issues two pipe-delimited `sinfo` calls and stitches the results.
- Shared `widgets/_bars.py` rendering helper (extracted from the job detail screen) reused by the dashboard.
- 66 new tests across `test_sinfo_parser.py`, `test_cluster_dashboard.py`, `test_first_run_wizard.py`, and `test_cli.py` (352 total).

### Fixed

- **`g`/`G` navigation now moves the cursor** to the first/last row of the job table. Previous binding was wrong on two counts: (1) it called `scroll_home`/`scroll_end`, which only adjust horizontal scroll for row-cursor `DataTable`s, and (2) it listed the key as `shift+g`, but xterm-style terminals deliver Shift+G as the literal character `G` (no modifier in the key event). Bindings now use `scroll_top`/`scroll_bottom` and accept both `G` and `shift+g` so they work in real terminals and the Textual test pilot. The same key-form fix was applied to `JobDetailScreen` and `LogScreen`.
- **Bottom detail panel no longer stuck on "No job selected"**: `JobDetail` is now seeded from the current cursor row inside `_update_display`. `DataTable` does not emit a `CursorMoved` event for its initial row-0 placement, so previously the panel stayed on its default text until the user pressed j/k. The empty-list case now reads "No jobs to display" instead of "No job selected".

### Added

- **`h`/`l` tab switching**: Vim-style keys cycle through profile tabs (no-op with a single profile).
- **`g`/`G` in `JobDetailScreen`**: Scroll detail body to top/bottom for consistency with the job table and log viewer.
- 7 new pilot tests in `test_app.py` covering `j`/`k`/`g`/`G`/`h`/`l` behavior.

## [0.3.0] - 2026-04-12

### Added

- **GPU column in job table**: Shows allocated GPUs per job (e.g., `4x l40s`) via new `gres` field in squeue format (`%b`).
- **Colored connection indicator**: ConnectionStatus widget now shows a colored dot (green = connected, red = error, yellow = loading) with profile name alongside host.
- **Badge-style status bar**: State counts render as colored badges with sort mode indicator icons.
- **Scrollable job detail screen**: Detail body uses `ScrollableContainer` so long output doesn't get cut off; j/k vim bindings for scrolling.
- **Section separators in detail screen**: Horizontal line separators between Time, Memory, GPUs, Resources, Schedule, and Log Files sections.
- **Log viewer stream indicator**: Header shows stream type (stdout/stderr) and follow mode (FOLLOW/PAUSED), updating dynamically on toggle.
- **Path truncation**: Work directory paths in the job table are truncated to the last 2 components for readability.
- 12 new unit tests for GPU display, gres parsing, and path truncation (231 total).

### Changed

- squeue format string now includes `%b` (gres) field by default.
- `SlurmJob` dataclass has new optional `gres` field and `gpu_display` property.
- `LogScreen` constructor accepts a `stream` parameter to distinguish stdout/stderr.
- `StatusBar.update_stats()` accepts `sort_mode` parameter.
- `ConnectionStatus` has new `profile_name` reactive field.
- Enhanced CSS: accent background on connection bar, border on detail panel, styled table cursor/header rows, darker status bar.
- Updated pyproject.toml description and version to 0.3.0.
- Rewritten README with current feature set, TOML config examples, and navigation flow documentation.

## [0.2.0] - 2026-04-12

### Added

- **Profile-based TOML configuration**: Support for multiple cluster profiles, each with its own SSH, log, and Slurm settings. JSON backward compatibility preserved.
- **Paramiko SSH client**: Replaced subprocess-based SSH with paramiko for programmatic connection management, connection reuse, key auth, and jump host support.
- **CLI with Click**: Added `--config`, `--profile`, `--host`, and `--list-profiles` command-line options.
- **Tabbed multi-profile UI**: Each cluster profile appears as its own tab when multiple profiles are configured.
- **Job detail panel**: Shows selected job's full info and resolved log path below the table.
- **Sacct caching**: Historical job data is cached and only re-fetched at a configurable `sacct_refresh_interval` (default 60s), reducing SSH load.
- **Configurable log viewer**: Log view command is now configurable per-profile via `log.view_command` (default: `tail -f {log_path}`).
- **Interactive filtering**: Filter jobs by state (`1`=Running, `2`=Pending, `3`=Completed, `4`=Failed, `0`=All) or by name search (`/` key).
- **Column sorting**: Press `s` to cycle sort by id, time, name, or state.
- **Status bar**: Shows job counts by state, active filters, and search query.
- **Extracted widget modules**: ConnectionStatus, JobTable, JobDetail, StatusBar, FilterBar in `widgets/` package.
- **External CSS**: Moved styles from inline Python to `app.tcss`.
- New config dataclasses: `SSHConfig`, `LogConfig`, `SlurmConfig`, `ProfileConfig`, `AppConfig`.
- `LogPathResolver.resolve_view_command()` for building configurable viewer commands.
- `config.example.toml` with documented TOML configuration format.

### Changed

- SSH wrapper now uses `paramiko.SSHClient` instead of `subprocess.run(["ssh", ...])`.
- Config format changed from flat JSON to profile-based TOML (JSON still supported for backward compatibility).
- `ConfigLoader.load()` now returns `AppConfig` (with profiles) instead of flat `Config`.
- `fetch_squeue_jobs()` and `fetch_sacct_jobs()` now accept `SSHClient` instead of bare host string.
- `JobAggregator` now takes `SSHClient` instead of host string.
- `LogPathResolver` now takes `LogConfig` instead of `Config`.
- Default refresh interval changed from 2s to 5s.
- Test count increased from 139 to 160.

### Removed

- Old flat `Config` and `LogPathConfig` dataclasses (replaced by profile-based system).
- `execute_ssh_command()` and `check_connection()` standalone functions (replaced by `SSHClient` class).

## [0.1.1] - 2026-03-31

### Fixed

- **Critical**: Made `refresh_data()` non-blocking by running SSH fetches in a background worker thread, preventing UI freezes during data refresh.
- Added overlap guard to prevent multiple concurrent refresh calls from piling up when SSH is slow.
- Fixed `sort_jobs_by_time()` to parse time strings numerically instead of using broken string comparison (e.g. "9:00:00" no longer sorts after "10:00:00"). Supports MM:SS, HH:MM:SS, and D-HH:MM:SS formats.
- Fixed shell injection vulnerability in log tail command by escaping the log path with `shlex.quote()`.
- Removed unused `import re` in `sacct_parser.py`.

## [0.1.0] - 2026-01-26

### Added

- Initial project setup and structure.
- tests folder
- Basic dependency management with `textual` and `rich`.
- project plan in plan.md
- claude.md for context and instructions.
- CHANGELOG.md for tracking changes.
- install pre-commit hooks for code quality.
- SSH wrapper module (`ssh_wrapper.py`) with timeout and connection error handling.
- Comprehensive test suite for SSH wrapper functionality.
- pytest as development dependency for testing.
- Squeue parser module (`squeue_parser.py`) for fetching and parsing Slurm job data.
- Sacct parser module (`sacct_parser.py`) for fetching and parsing historical Slurm job data.
- Job aggregator module (`job_aggregator.py`) for merging active and historical job data.
- `SlurmJob` dataclass for structured job representation.
- `JobAggregator` class for unified job data fetching with automatic deduplication.
- Support for parsing pipe-delimited squeue output into JSON-compatible structures.
- Support for parsing whitespace-delimited sacct output with flexible formatting.
- Active jobs take precedence over historical data when duplicate job IDs exist.
- Helper functions for filtering, sorting, and searching jobs.
- Configuration system (`config.py`) with JSON-based config loading.
- `Config` and `LogPathConfig` dataclasses for structured configuration.
- `ConfigLoader` class with default path search and fallback to defaults.
- Log path resolver (`log_path_resolver.py`) with token-based pattern matching.
- `LogPathResolver` class supporting {job_id}, {work_dir}, and {project_name} tokens.
- Project-specific log path patterns with automatic detection from work_dir.
- Support for complex nested directory structures via configuration.
- 24 unit tests for squeue parser with mocked SSH commands.
- 29 unit tests for sacct parser covering various states and edge cases.
- 28 unit tests for job aggregator covering merge logic and utilities.
- TUI application (`app.py`) built with Textual framework.
- `SlurmhubApp` main application class with reactive UI.
- `ConnectionStatus` widget displaying host, status, and last update time.
- `JobTable` custom DataTable with color-coded job states.
- Automatic data refresh with configurable interval.
- Async data fetching using Textual workers to keep UI responsive.
- Rich styling for job states (green=RUNNING, yellow=PENDING, red=FAILED, etc.).
- Keyboard shortcuts: q (quit), r (refresh), ? (help).
- Real-time status indicators with emoji icons.
- Vim-style navigation keybindings (j/k for up/down, g/G for top/bottom).
- Log viewing feature with Enter key to tail job logs.
- App suspension using `with self.suspend()` for seamless shell integration.
- SSH tail command execution with `-t` flag for proper TTY handling.
- Automatic return to TUI after log viewing with state preservation.
- Log path resolution integration for automatic log file discovery.
- User-friendly error messages for missing log files or unresolved paths.
- Comprehensive SSH setup documentation in README.
- SSH key generation guide (ssh-keygen, ssh-copy-id).
- SSH ControlMaster optimization guide for faster polling.
- Step-by-step verification instructions.
- Example configuration file (config.example.json).
- Comprehensive configuration examples document (docs/configuration-examples.md):
  - Basic and standard configurations
  - SSH host alias usage
  - Project-specific log path patterns
  - Complex directory structures
  - High-frequency and slow-network configurations
  - Token reference and common patterns
  - Troubleshooting guide
  - Best practices
- 20 unit tests for config loader covering JSON parsing and defaults.
- 18 unit tests for log path resolver covering token replacement and patterns.
