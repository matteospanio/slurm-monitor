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
