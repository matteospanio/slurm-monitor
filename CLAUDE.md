This repository is for a terminal-based user interface (TUI) application designed to monitor and display Slurm job statuses in real-time. The application leverages the Textual framework for building rich terminal applications and provides an intuitive interface for users to track their jobs on a Slurm-managed cluster.

## Context

Before taking actions, skim `CHANGELOG.md` for the latest release notes and the Sphinx documentation under `docs/` for user-facing behavior. After implementing code changes, update `CHANGELOG.md` (and `README.md` when the public surface changes), then create a git commit (pre-commit hooks will run automatically).

When you add new features, create a new test under `tests/` to verify the feature works as intended.

## Tools

Use `uv` for running the application, `pytest` for the test suite, `pre-commit` for code quality, and `sphinx-build` (via `uv sync --group docs`) for building the documentation site locally.

## Demo mode

`uv run slurmhub --demo` launches the app against a built-in fixture dataset (no SSH needed). Useful for screenshots, demos, and reproducing UI bugs without a live cluster. Screenshot generation for the docs lives at `docs/scripts/generate_screenshots.py`.
