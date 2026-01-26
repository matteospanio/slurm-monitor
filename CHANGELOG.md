# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> The *Unreleased* section is for changes that are not yet released, but are going to be released in the next version.

## [Unreleased] - 2026-01-26

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
- 24 unit tests for squeue parser with mocked SSH commands.
- 29 unit tests for sacct parser covering various states and edge cases.
- 28 unit tests for job aggregator covering merge logic and utilities.
