This repository is for a terminal-based user interface (TUI) application designed to monitor and display Slurm job statuses in real-time. The application leverages the Textual framework for building rich terminal applications and provides an intuitive interface for users to track their jobs on a Slurm-managed cluster.

## Context

Before taking actions read the plan.md file for context and instructions. Look for the latest updates there. After implementing any code changes, ensure to update the plan.md file with progress or completion status, create a git commit (use pre-commit hooks if available), and update the CHANGELOG and the README when needed.

When you add new features create a new test to verify the feature works as intended. Tests should be located in the tests/ directory.

## Tools

Use uv for running the application, pytest for testing, and pre-commit hooks for code quality.
