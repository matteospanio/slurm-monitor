# Slurm TUI Monitor

A terminal-based user interface (TUI) application for monitoring and displaying Slurm job statuses in real-time.

## Features

- Real-time monitoring of Slurm jobs
- SSH-based remote command execution with robust error handling
- Intuitive terminal interface built with Textual

## Development Status

This project is in active development. See [plan.md](plan.md) for the full development roadmap.

### Completed Features

- **Epic 1: Foundation & Environment Setup**
  - ✅ Task 1.1: Project initialization with uv
  - ✅ Task 1.2: SSH wrapper prototype with timeout and error handling

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Clone the repository
git clone <repository-url>
cd slurm_monitor

# Install dependencies
uv sync

# Run tests
uv run pytest
```

## Development

### Running Tests

```bash
uv run pytest
```

### Code Quality

This project uses pre-commit hooks for code quality:

```bash
# Install pre-commit hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Requirements

- Python >= 3.12
- SSH client installed and configured
- Access to a Slurm cluster

## License

TBD

## Contributing

See [CLAUDE.md](CLAUDE.md) for development guidelines and project context.
