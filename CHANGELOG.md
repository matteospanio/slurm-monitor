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
- `SlurmJob` dataclass for structured job representation.
- Support for parsing pipe-delimited squeue output into JSON-compatible structures.
- 24 unit tests for squeue parser with mocked SSH commands.
