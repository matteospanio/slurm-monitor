# Project Plan: Slurm TUI Monitor

**Role**: DevOps Project Manager
**Methodology**: Agile Epics

This document outlines the development roadmap broken down into verifiable epics. Each task includes a "Verification" step to ensure functionality before integration.

## 📦 Epic 1: Foundation & Environment Setup

Goal: Initialize the project structure, dependency management, and prove connectivity capability.

- [x] Task 1.1: Project Initialization

  - Initialize project using uv.
  - Define dependencies: textual, rich.
  - Create directory structure: src/, tests/.
  - Verification: uv sync runs successfully; import textual works in a test script.

- [x] Task 1.2: SSH Wrapper Prototype

  - Create a simple Python script using subprocess to run ssh <host> echo "success".
  - Handle ssh timeout and connection errors (e.g., host unreachable).
  - Verification: Script prints "success" when connected to the cluster and handles errors gracefully if VPN/Network is down.

## ⚙️ Epic 2: Core Data Engine (Backend)

Goal: Reliably fetch and parse raw data from Slurm without blocking the main thread.

- [x] Task 2.1: Squeue Parser

  - Implement method to run: squeue --me -o "%i|%j|%T|%M|%o|%Z" --noheader.
  - Create a parser to convert the pipe-delimited string into a list of Dictionaries/Objects.
  - Verification: Unit test with mocked stdout returns correct JSON structure for active jobs.

- [x] Task 2.2: Sacct Parser (History)

  - Implement method to run: sacct -X --format=JobID,JobName,State,Elapsed,WorkDir --units=M -n.
  - Handle whitespace formatting specific to sacct.
  - Verification: Unit test accurately parses a sample sacct output string into structured data.

- [x] Task 2.3: Data Aggregation Service

  - Create a class that merges squeue (active) and sacct (history) results.
  - Ensure active jobs take precedence over history if duplicates exist.
  - Verification: Running the service returns a unified list of jobs sorted by time.

## 🔧 Epic 3: Configuration & Path Resolution

Goal: Make the application flexible enough to handle complex directory structures.

- [x] Task 3.1: Config Loader

  - Implement logic to load ~/.config/slurm_monitor/config.json.
  - Define defaults if file is missing.
  - Verification: App reads remote_host from JSON; falls back to defaults if file missing.

- [x] Task 3.2: Log Path Strategy Pattern

  - Implement the logic to interpret {work_dir}, {job_id}, and {project_name} tokens.
  - Implement logic to check specific_projects mapping first, then default_pattern.
  - Verification: Test case: Passing work_dir="/home/user/project1" and job_id="123" correctly returns /home/user/project1/logs/out/123.txt based on config.

## 🖥️ Epic 4: User Interface (Frontend)

Goal: specific Visual implementation using Textual.

- [x] Task 4.1: App Skeleton & Header

  - Create App class inheriting from textual.app.App.
  - Implement Header with: Connection Name, Last Updated Timestamp, and Loading Spinner.
  - Verification: App launches, shows TUI, and spinner animates.

- [x] Task 4.2: Data Table Implementation

  - Implement DataTable widget.
  - Map data columns: ID, Name, Status, Time.
  - Apply Rich styling (Green for Running, Red for Fail, etc.).
  - Verification: Hardcoded mock data renders correctly with colors in the terminal.

- [x] Task 4.3: Async Data Binding

  - Connect Epic 2 (Data Engine) to Epic 4 (UI) using set_interval.
  - Ensure UI remains responsive while ssh command runs in background.
  - Verification: App updates list every 2 seconds without freezing the cursor.

## 🎮 Epic 5: Interaction & Control

Goal: Implement Vim-like navigation and the core "Tail" feature.

- [x] Task 5.1: Vim Navigation

  - Bind j/k to row selection movement.
  - Bind g/G to top/bottom scroll.
  - Verification: User can navigate the table without using arrow keys.

- [x] Task 5.2: The "Tail" Context Switch

  - Implement Enter key handler.
  - Use driver.suspend_application_mode() to drop to shell.
  - Construct and run ssh -t <host> tail -f <path>.
  - Verification: Pressing Enter opens a full-screen tail; Ctrl+C returns exactly to the previous TUI state.

## 📚 Epic 6: Documentation & Onboarding

Goal: Ensure the user can actually connect.

- [x] Task 6.1: SSH Key Guide

  - Write README.md section on ssh-keygen and ssh-copy-id.
  - Explain ~/.ssh/config ControlMaster (optional optimization for faster polling).
  - Verification: A standard user can follow instructions to set up password-less auth.

- [x] Task 6.2: Config Examples

  - Provide config.example.json covering standard and complex project structures.

## 🐛 Epic 7: Bug Fixes & Performance

Goal: Fix bugs and performance issues found during usage.

- [x] Task 7.1: Fix UI Freezing During Refresh

  - Moved SSH fetch calls from the synchronous event loop to a Textual `run_worker(thread=True)` background thread.
  - Added `_refresh_in_progress` guard to prevent overlapping refresh cycles.
  - Verification: UI stays responsive during SSH calls; no concurrent refresh pile-up.

- [x] Task 7.2: Fix Time Sorting Bug

  - Replaced string-based time comparison in `sort_jobs_by_time()` with numeric parsing via `_time_to_seconds()`.
  - Supports MM:SS, HH:MM:SS, and D-HH:MM:SS formats.
  - Verification: 10 new unit tests pass covering all time formats and edge cases.

- [x] Task 7.3: Fix Shell Injection in Tail Command

  - Applied `shlex.quote()` to the log path in the SSH tail command.
  - Verification: Paths with special characters are safely escaped.

- [x] Task 7.4: Remove Unused Import

  - Removed unused `import re` from `sacct_parser.py`.
  - Verification: All 139 tests pass.

- [x] Task 7.5: Graceful SSH Error Handling in App

  - Wrapped `_fetch_jobs()` SSH calls in try/except so connection/timeout errors are returned as data instead of crashing the app.
  - The worker now always succeeds; errors are displayed via the UI notification and connection status widget.
  - Verification: App no longer crashes when SSH host is unreachable; 4 new unit tests pass.

- [x] Task 8.8: Parse ~/.ssh/config for Host Aliases

  - Updated `_build_connect_kwargs()` to read `~/.ssh/config` via `paramiko.SSHConfig`.
  - Resolves host aliases to real hostnames, usernames, ports, identity files, and proxy commands.
  - Explicit `SSHConfig` fields still override SSH config values.
  - Verification: 8 new unit tests pass covering alias resolution, overrides, proxy commands, and missing config.

- [x] Task 7.6: Fix Worker State Comparison Using Enum

  - `on_worker_state_changed` compared `event.state` against string literals (`"success"`, `"error"`, `"cancelled"`) but Textual uses `WorkerState` enum values.
  - Replaced string comparisons with `WorkerState.SUCCESS`, `WorkerState.ERROR`, `WorkerState.CANCELLED`.
  - This was the reason jobs were fetched but never displayed in the UI.
  - Verification: All 172 tests pass; jobs now appear in the table.

- [x] Task 7.7: Fix Enter Key Not Opening Log Viewer

  - DataTable's built-in `enter` binding (`select_cursor`) was intercepting the key before the app-level `action_view_logs` binding.
  - Added `on_data_table_row_selected` handler to catch DataTable's RowSelected event and delegate to `action_view_logs`.
  - Verification: Pressing Enter on a job row now opens the log viewer.

- [x] Task 5.3: In-App Log Viewer Screen

  - Replaced the suspend-to-shell `tail -f` approach with an in-TUI `LogScreen`.
  - New `LogScreen` uses Textual's `RichLog` widget and streams log lines via paramiko channel.
  - Bindings: `Escape`/`q` to return to the main screen.
  - Removed `subprocess` and `shlex` dependencies from app.py.
  - Verification: 5 new unit tests pass; Enter opens logs inside the TUI.

## 🔍 Epic 9: Extended Job Details via scontrol

Goal: Show rich job resource usage (time, memory, CPUs) and use real log paths from Slurm.

- [x] Task 9.1: scontrol Parser and JobDetails Dataclass

  - New `scontrol_parser.py` with `JobDetails` dataclass, `parse_scontrol_output()`, memory parsing, and `fetch_job_details()`.
  - Fetches `scontrol show job` for metadata and `sstat` for actual memory usage of running jobs.
  - Computes time percentage (RunTime/TimeLimit) and memory percentage (MaxRSS/ReqTRES).
  - Made `_time_to_seconds` public as `time_to_seconds` for reuse.
  - Verification: 31 new unit tests pass.

- [x] Task 9.2: Enhanced Job Detail Panel

  - Expanded `JobDetail` widget to render time/memory progress bars, CPUs, partition, nodes, submit/start times, StdOut/StdErr paths.
  - Detail panel auto-sizes up to 10 lines.
  - Details fetched via background worker on cursor move.
  - Verification: Detail panel shows resource usage with colored bars.

- [x] Task 9.3: Log Viewer Uses scontrol StdOut Path

  - `action_view_logs` now uses the real `StdOut` path from scontrol instead of config-based pattern resolver.
  - Falls back to `LogPathResolver` when scontrol data is unavailable.
  - Verification: Enter opens the actual Slurm log file.

- [x] Task 9.4: Redesigned Navigation Flow

  - New flow: job table → Enter → JobDetailScreen (scontrol stats) → `o` stdout / `e` stderr → LogScreen → Escape back.
  - New `JobDetailScreen` shows full scontrol stats: time/memory bars, CPUs, partition, nodes, schedule, command, log paths.
  - `LogScreen` now has vim keybindings (j/k/g/G) for scrolling and `f` to toggle follow mode.
  - Simplified `JobDetail` bottom panel to basic summary (detail screen has full stats).
  - Removed detail-fetching-on-cursor-move from app.py (detail screen manages its own fetch).
  - Verification: 208 tests pass; 3-screen navigation works correctly.

- [x] Task 9.5: GPU Utilization Display

  - Added `GpuInfo` dataclass and `parse_tres_gpu()` to extract GPU count/type from TRES.
  - `fetch_job_details()` runs `srun --jobid=<id> --overlap nvidia-smi` for running GPU jobs.
  - `parse_nvidia_smi_output()` parses per-GPU utilization and memory usage.
  - `JobDetailScreen` shows GPU section with per-GPU utilization bars and memory bars.
  - Verification: 219 tests pass; GPU jobs show live utilization data.

## 🔄 Epic 8: Full Refactoring - Configurable Multi-Profile Architecture

Goal: Make the app fully configurable with multi-cluster support, paramiko SSH, and improved UX.

- [x] Task 8.1: Profile-Based TOML Configuration

  - Replaced flat JSON config with profile-based TOML format.
  - New dataclasses: SSHConfig, LogConfig, SlurmConfig, ProfileConfig, AppConfig.
  - JSON backward compatibility preserved via _from_legacy_json().
  - Verification: 37 config tests pass covering TOML, JSON, profile merging.

- [x] Task 8.2: Click CLI

  - Added cli.py with --config, --profile, --host, --list-profiles options.
  - Updated pyproject.toml entry point.
  - Verification: `slurm-monitor --help` and `--list-profiles` work correctly.

- [x] Task 8.3: Paramiko SSH Client

  - Replaced subprocess SSH with paramiko SSHClient class.
  - Supports connection reuse, key auth, jump hosts, custom ports.
  - Verification: 15 SSH wrapper tests pass covering connect, execute, close.

- [x] Task 8.4: Updated Parsers and Aggregator

  - fetch_squeue_jobs/fetch_sacct_jobs now accept SSHClient.
  - JobAggregator takes SSHClient instead of host string.
  - LogPathResolver takes LogConfig instead of Config.
  - Verification: All 160 tests pass.

- [x] Task 8.5: Tabbed Multi-Profile UI

  - TabbedContent with one tab per profile (single profile = no tabs).
  - Each tab has its own ConnectionStatus, JobTable, JobDetail.
  - Sacct caching with configurable sacct_refresh_interval.
  - Configurable log viewer via log.view_command.
  - Verification: App launches with tabbed layout.

- [x] Task 8.6: Filtering, Search, and Sort

  - State filter toggle keys (1-4, 0 for all).
  - Name search via / key with FilterBar widget.
  - Sort cycling via s key (id/time/name/state).
  - StatusBar showing job counts and active filters.
  - Verification: Filtering and sort work interactively.

- [x] Task 8.7: Widget Extraction

  - Extracted widgets to widgets/ package: ConnectionStatus, JobTable, JobDetail, StatusBar, FilterBar.
  - Moved CSS to external app.tcss file.
  - Verification: All 160 tests pass.

## 🎨 Epic 10: UI Polish & Visual Improvements

Goal: Make the TUI more visually polished and information-dense.

- [x] Task 10.1: Enhanced CSS Styling

  - Added accent background to ConnectionStatus, subtle border to JobDetail panel.
  - Styled DataTable cursor/header rows.
  - Darker background for StatusBar.
  - Verification: Visual inspection confirms improved contrast and structure.

- [x] Task 10.2: Improved ConnectionStatus

  - Added colored dot indicator: green = connected, red = error, yellow = loading, hollow = not connected.
  - Displays profile name alongside host: `● dei (login.dei.unipd.it) │ Updated: 15:42:07`.
  - Verification: 231 tests pass.

- [x] Task 10.3: Better JobTable

  - Added GPU column showing allocated GPUs (e.g., `4x l40s`) via new `gres` field in squeue format.
  - Truncated work_dir paths to last 2 components (e.g., `../tmp/mxlGPT`).
  - Right-aligned Time column for easier scanning.
  - Verification: 231 tests pass; 6 new tests for truncate_path, 7 new tests for gpu_display/gres parsing.

- [x] Task 10.4: Richer StatusBar

  - Badge-style state counts with colored backgrounds (green/yellow/blue/red).
  - Sort mode indicator with icons (#, ⏱, A-Z, ●).
  - Verification: 231 tests pass.

- [x] Task 10.5: Scrollable JobDetailScreen

  - Replaced plain Static body with ScrollableContainer for long detail views.
  - Added horizontal line separators (─) between sections.
  - Added j/k vim bindings for scrolling within the detail screen.
  - Verification: 231 tests pass.

- [x] Task 10.6: Improved LogScreen Header

  - Header now shows stream type (stdout/stderr), follow mode indicator (FOLLOW/PAUSED), and path.
  - Header updates dynamically when toggling follow mode.
  - Verification: 231 tests pass.

## 🔐 Epic 11: Interactive SSH Password Authentication

Goal: Allow users to authenticate via password/passphrase when no SSH agent or key is available.

- [x] Task 11.1: SSHAuthenticationError and Runtime Credentials

  - Added `SSHAuthenticationError(SSHConnectionError)` subclass to distinguish auth failures.
  - Added `set_credentials(password, passphrase)` method on `SSHClient` for runtime credential injection (memory only).
  - Runtime credentials included in connect kwargs and jump host kwargs.
  - Runtime passphrase overrides config passphrase.
  - Verification: 11 new tests pass covering exception hierarchy, credential storage, kwargs injection, and jump host support.

- [x] Task 11.2: PasswordPromptScreen Modal

  - New `PasswordPromptScreen(ModalScreen)` in `widgets/password_prompt.py`.
  - Displays host/username, masked password input, dismisses on Enter (submit) or Escape (cancel).
  - Inline CSS for centered dialog overlay.
  - Verification: 4 new tests pass.

- [x] Task 11.3: App Integration

  - Auth failure detection in `on_worker_state_changed` via `isinstance(error, SSHAuthenticationError)`.
  - Pushes `PasswordPromptScreen` on first auth failure (up to 3 attempts).
  - `_handle_password_result` callback injects credentials and triggers retry.
  - Successful connection resets auth attempt counter.
  - Verification: 245 tests pass.

## 🔄 Epic 12: Stable Cursor + Cluster Queue Overview

Goal: Fix cursor reset on table refresh and add cluster-wide queue monitoring with pending job ranking.

- [x] Task 12.1: Preserve Cursor Position During Refresh

  - Track selected job_id in `JobTable._current_job_ids` before `clear()`.
  - After repopulating rows, restore cursor to the same job via `move_cursor()`.
  - If the selected job disappeared, clamp cursor to nearest valid row.
  - Verification: 7 new async Textual pilot tests in `test_job_table.py`.

- [x] Task 12.2: Queue Stats Data Layer

  - Extended `SlurmJob` with optional pending fields: `pending_reason`, `priority`, `qos`, `submit_time`, `queue_rank`.
  - New module `queue_stats.py` with `ClusterQueueStats` dataclass and fetch functions:
    - `fetch_cluster_queue_stats()` — counts RUNNING/PENDING via `squeue --noheader -o "%T"`.
    - `fetch_pending_details()` — fetches reason, priority, QOS, submit time for user's pending jobs.
    - `compute_queue_ranks()` — determines 1-based queue rank by sorting all pending jobs by priority.
  - Verification: 16 new tests in `test_queue_stats.py`.

- [x] Task 12.3: Refresh Cycle Integration

  - Replaced 3-tuple return from `_fetch_jobs()` with `FetchResult` dataclass.
  - Added cluster queue stats fetch (cached ~30s) and pending job enrichment to the refresh cycle.
  - Queue stats and pending details are non-critical — errors don't break the main job fetch.
  - Updated `on_worker_state_changed()` to unpack `FetchResult`.
  - Verification: All 4 existing `test_app.py` tests updated and passing.

- [x] Task 12.4: UI Updates

  - `StatusBar` now shows cluster-wide totals: "Cluster: N running, M pending".
  - `JobTable` has two new columns: "Reason" and "Rank" (populated only for PENDING jobs).
  - `JobDetail` panel shows pending reason, queue rank, QOS, priority, and submit time for PENDING jobs.
  - Verification: 273 tests pass. Pre-commit hooks pass.

## 🎮 Epic 13: Vim Navigation Polish

Goal: Make the navigation match vim conventions across the whole interface.

- [x] Task 13.1: Fix `g`/`G` to Move Cursor to Top/Bottom of Table

  - App bindings were wired to `DataTable.action_scroll_home`/`action_scroll_end`, which (for a row-cursor table) only adjust horizontal scroll — the cursor stayed put.
  - Switched the `g`/`G` bindings to `action_scroll_top`/`action_scroll_bottom`, the cursor-moving variants.
  - Verification: New `test_g_moves_cursor_to_first_row` and `test_shift_g_moves_cursor_to_last_row` pilot tests pass.

- [x] Task 13.1b: Bind `G` Directly (Not Just `shift+g`)

  - Real terminals send the literal character `G` for Shift+G (xterm parser only produces a `shift+letter` form when alt is also held — see `_xterm_parser.py`). The original `shift+g` binding never fired in actual use.
  - Bindings now use the form `"G,shift+g"` so they match both the terminal-delivered `G` and the synthetic event Textual's test pilot generates. Applied to `app.py`, `JobDetailScreen`, and `LogScreen`.
  - Added `test_shift_plus_g_alias_also_works` alongside the existing `test_shift_g_moves_cursor_to_last_row` (now pressing the literal `G`).
  - Verification: 284 tests pass.

- [x] Task 13.3: Seed `JobDetail` Panel from Cursor on Render

  - `DataTable` doesn't fire `CursorMoved` for its initial row-0 placement, so the bottom detail panel sat on its default "No job selected" text until the user pressed j/k.
  - `_update_display` now reads `table.cursor_row` and calls `detail.set_job(...)` directly so the panel reflects the selected row on first paint, after a refresh, and after a tab switch.
  - `JobDetail.set_job` gained a `has_jobs` flag so the empty-list case renders "No jobs to display" instead of "No job selected".
  - Verification: 286 tests pass (2 new pilot tests).

- [x] Task 13.2: Add `h`/`l` Tab Switching

  - New `action_previous_tab` / `action_next_tab` bound to `h` / `l`, cycling through profile tabs with wrap-around.
  - No-op when only one profile is configured.
  - `JobDetailScreen` also gained `g`/`G` for scroll top/bottom to keep keybindings consistent across screens.
  - Verification: 283 tests pass (7 new pilot tests for `j`/`k`/`g`/`G`/`h`/`l`).

## 📊 Epic 14: Cluster Dashboard

Goal: Give users a single-keystroke view of cluster capacity (CPUs, GPUs, memory), per-partition state, and per-node detail before open-sourcing the project.

- [x] Task 14.1: `sinfo_parser` Module

  - New module with `PartitionStats`, `NodeStats`, `ClusterCapacity` dataclasses.
  - Two `sinfo` calls (`-h -o "%R|%D|%C|%G|%m|%a"` and `-h -N -o "%N|%R|%T|%C|%e|%m|%G|%E"`) parsed and stitched into a single capacity snapshot.
  - State suffix stripping (`mixed*`, `idle~`, …) and GRES parsing covering `(null)`, `gpu:4`, `gpu:l40s:4`, and `gpu:a100:8(IDX:0-7)`.
  - Verification: 37 unit tests in `test_sinfo_parser.py`.

- [x] Task 14.2: `ClusterDashboardScreen` Widget

  - Full-screen `Screen` (not `ModalScreen`) modelled on `JobDetailScreen`.
  - Capacity block with three colored bars (CPU/GPU/Memory) plus a "12 up · 1 down · 0 drain" footer line.
  - Partition `DataTable` and per-node `DataTable` populated from the cached `ProfileTab` data.
  - `set_interval(60s)` auto-refresh; `r` triggers an immediate fetch; `j`/`k`/`g`/`G` scroll the body; `Esc`/`q` returns.
  - Shared `_render_bar` helper extracted to `widgets/_bars.py` and reused from the job detail screen.

- [x] Task 14.3: App Integration

  - `d` binding on the main app pushes the dashboard for the active profile, seeding it from `ProfileTab` cached data so re-opening is instant.
  - `_fetch_jobs` now runs `fetch_sinfo` opportunistically (cached ~60 s) alongside the existing squeue/sacct/queue-stats path. Failures are non-critical.
  - `FetchResult` extended with `cluster_capacity`, `partitions`, `nodes`, `sinfo_fetched`.
  - Verification: 6 dashboard pilot tests and updates to `test_app.py`; 343 tests pass at this milestone.

## 🧙 Epic 15: First-Run Setup Wizard

Goal: Replace the silent "empty default profile" fallback with an interactive Textual modal so newcomers can connect on the first launch.

- [x] Task 15.1: `ConfigLoader.locate`

  - Returns `(path, found)` without falling back to the empty default profile. Keeps the existing `load()` fallback for tests and edge cases.
  - Used by `cli.main` to decide whether to launch the wizard.

- [x] Task 15.2: `FirstRunWizardScreen` Modal

  - `ModalScreen[Optional[ProfileConfig]]` with inputs for profile name, host, username, port, key path, and log pattern. Defaults: ed25519 key if it exists, `getpass.getuser()` username, log pattern `{work_dir}/logs/{job_id}.out`.
  - Three buttons: `Test connection` (worker thread + `SSHClient.check_connection`), `Save and continue`, `Cancel`. Validation errors (missing host, non-numeric port) appear in an inline status line; the modal stays open until the user fixes them or cancels.
  - Companion `ConfirmScreen` (`y`/`n`/`Esc`) for the "Add another cluster?" loop.

- [x] Task 15.3: CLI Orchestration

  - `run_first_run_wizard(save_path)` runs a tiny `WizardApp` that loops the wizard + confirm screens, then persists the collected profiles via `ConfigLoader.save_toml`.
  - `cli.main` invokes the wizard when `locate` reports `found=False` and `--config`/`--host` were not supplied. Cancellation exits 1 with a friendly message.
  - Verification: 16 wizard tests + 7 CLI tests; 352 tests pass overall.
