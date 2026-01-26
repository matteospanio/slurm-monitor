# Slurm TUI Monitor

A terminal-based user interface (TUI) application for monitoring and displaying Slurm job statuses in real-time.

## Features

- 🚀 Real-time monitoring of Slurm jobs with automatic refresh
- 📊 Color-coded job states (RUNNING, PENDING, COMPLETED, FAILED, etc.)
- 🔒 SSH-based remote command execution with robust error handling
- ⚙️ Flexible configuration via JSON files
- 📁 Intelligent log file path resolution with project-specific patterns
- ⌨️ Keyboard-driven interface with Vim-like navigation
- 🔍 Integrated log viewer with tail -f for real-time log monitoring
- 💻 Intuitive terminal UI built with Textual

## Usage

Run the application:

```bash
# Using uv
uv run slurm-monitor

# Or after installation
slurm-monitor
```

### Keyboard Shortcuts

- `q` - Quit application
- `r` - Manually refresh job data
- `j`/`k` - Navigate down/up (Vim-style)
- `g`/`G` - Jump to top/bottom of list
- `↑`/`↓` - Navigate through jobs (arrow keys)
- `Enter` - View job logs with `tail -f` (press Ctrl+C to return)
- `?` - Show help

### Configuration

Create a config file at `~/.config/slurm_monitor/config.json`:

```json
{
  "remote_host": "your-cluster.edu",
  "ssh_timeout": 10,
  "refresh_interval": 2,
  "log_paths": {
    "default_pattern": "{work_dir}/logs/{job_id}.out",
    "specific_projects": {
      "ml_project": "{work_dir}/ml/logs/{job_id}.log"
    }
  }
}
```

## Development Status

This project is in active development. See [plan.md](plan.md) for the full development roadmap.

### Completed Features

- **Epic 1: Foundation & Environment Setup** ✅
  - ✅ Task 1.1: Project initialization with uv
  - ✅ Task 1.2: SSH wrapper prototype with timeout and error handling

- **Epic 2: Core Data Engine (Backend)** ✅
  - ✅ Task 2.1: Squeue parser for active job data
  - ✅ Task 2.2: Sacct parser for historical job data
  - ✅ Task 2.3: Data aggregation service with automatic deduplication

- **Epic 3: Configuration & Path Resolution** ✅
  - ✅ Task 3.1: Config loader with JSON support and defaults
  - ✅ Task 3.2: Log path strategy pattern with token replacement

- **Epic 4: User Interface (Frontend)** ✅
  - ✅ Task 4.1: App skeleton & header with connection status
  - ✅ Task 4.2: DataTable implementation with Rich styling
  - ✅ Task 4.3: Async data binding with automatic refresh

- **Epic 5: Interaction & Control** ✅
  - ✅ Task 5.1: Vim navigation (j/k, g/G keybindings)
  - ✅ Task 5.2: Tail feature for viewing job logs

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
