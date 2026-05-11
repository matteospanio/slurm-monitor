# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> The *Unreleased* section is for changes that are not yet released, but are going to be released in the next version.

## [Unreleased]

### Fixed

- **`g`/`G` navigation now moves the cursor** to the first/last row of the job table. Previous binding was wrong on two counts: (1) it called `scroll_home`/`scroll_end`, which only adjust horizontal scroll for row-cursor `DataTable`s, and (2) it listed the key as `shift+g`, but xterm-style terminals deliver Shift+G as the literal character `G` (no modifier in the key event). Bindings now use `scroll_top`/`scroll_bottom` and accept both `G` and `shift+g` so they work in real terminals and the Textual test pilot. The same key-form fix was applied to `JobDetailScreen` and `LogScreen`.

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
- `SlurmMonitorApp` main application class with reactive UI.
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
