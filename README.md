# Slurm TUI Monitor

A terminal-based user interface (TUI) application for monitoring and displaying Slurm job statuses in real-time.

## Features

- Real-time monitoring of Slurm jobs with automatic refresh
- Color-coded job states (RUNNING, PENDING, COMPLETED, FAILED, etc.)
- Multi-profile support for monitoring multiple clusters
- SSH-based remote command execution via paramiko with connection reuse
- Flexible configuration via TOML files (JSON backward compatible)
- GPU allocation column showing allocated GPUs per job
- In-TUI log viewer streaming stdout/stderr via paramiko channels
- Detailed job view with scontrol stats: time/memory progress bars, GPU utilization, resource usage
- Interactive filtering by state and name search
- Column sorting (id, time, name, state)
- Vim-style keyboard navigation throughout

## Usage

```bash
# Using uv
uv run slurm-monitor

# With a specific profile
uv run slurm-monitor --profile dei

# List configured profiles
uv run slurm-monitor --list-profiles

# Or after installation
slurm-monitor
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit application |
| `r` | Manually refresh job data |
| `j`/`k` | Navigate down/up (Vim-style) |
| `g`/`G` | Jump to top/bottom of list |
| `h`/`l` | Switch to previous/next profile tab |
| `Enter` | Open job detail screen |
| `o` | View stdout log (from detail screen) |
| `e` | View stderr log (from detail screen) |
| `f` | Toggle follow mode (in log viewer) |
| `/` | Search/filter jobs by name |
| `1`-`4` | Filter by state (Running/Pending/Completed/Failed) |
| `0` | Show all jobs |
| `s` | Cycle sort mode (id/time/name/state) |
| `?` | Show help |
| `Esc` | Go back / close screen |

### Navigation Flow

1. **Job table** - Browse all jobs, filter and sort
2. **Job detail screen** (`Enter`) - View scontrol stats: time/memory bars, GPU utilization, resources, schedule, log paths
3. **Log viewer** (`o`/`e`) - Stream stdout or stderr with follow mode

### Configuration

Create a config file at `~/.config/slurm_monitor/config.toml`:

```toml
[defaults]
ssh_timeout = 10
refresh_interval = 5
sacct_refresh_interval = 60

[defaults.log]
default_pattern = "{work_dir}/logs/out/{job_id}.txt"
view_command = "tail -f {log_path}"

[profiles.dei]
host = "dei"
```

For hosts defined in `~/.ssh/config`, the app automatically resolves hostnames, usernames, ports, identity files, and proxy commands.

For more configuration examples and use cases, see [Configuration Examples](docs/configuration-examples.md).

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

## SSH Setup

For seamless operation, you need passwordless SSH access to your Slurm cluster.

### 1. Generate SSH Key (if you don't have one)

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

### 2. Copy Your Public Key to the Cluster

```bash
ssh-copy-id your-username@your-cluster.edu
```

### 3. Configure SSH (Optional but Recommended)

Create or edit `~/.ssh/config` to simplify connections:

```ssh-config
Host slurm-cluster
    HostName your-cluster.edu
    User your-username
    IdentityFile ~/.ssh/id_ed25519

    # ControlMaster for faster connections (optional optimization)
    ControlMaster auto
    ControlPath ~/.ssh/control-%r@%h:%p
    ControlPersist 10m
```

Then reference the alias in your TOML config:

```toml
[profiles.cluster]
host = "slurm-cluster"
```

### 4. Verify Setup

```bash
# Should connect without password
ssh slurm-cluster 'squeue --me'
```

## Development

### Running Tests

```bash
uv run pytest
```

### Code Quality

This project uses pre-commit hooks for code quality:

```bash
pre-commit install
pre-commit run --all-files
```

## Requirements

- Python >= 3.12
- SSH client installed and configured
- Access to a Slurm cluster

## Development Status

This project is in active development. See [plan.md](plan.md) for the full development roadmap.

## License

TBD

## Contributing

See [CLAUDE.md](CLAUDE.md) for development guidelines and project context.
