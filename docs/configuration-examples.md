# Configuration Examples

This document provides various configuration examples for different use cases.

## Basic Configuration

Minimal configuration with defaults:

```json
{
  "remote_host": "hpc.example.edu"
}
```

All other settings will use defaults:
- `ssh_timeout`: 10 seconds
- `refresh_interval`: 2 seconds
- `log_paths.default_pattern`: `{work_dir}/logs/{job_id}.out`

## Standard Configuration

Typical setup for most users:

```json
{
  "remote_host": "cluster.university.edu",
  "ssh_timeout": 10,
  "refresh_interval": 2,
  "log_paths": {
    "default_pattern": "{work_dir}/logs/{job_id}.out"
  }
}
```

## Configuration with SSH Host Alias

Using SSH config aliases (recommended):

**~/.ssh/config:**
```ssh-config
Host my-cluster
    HostName long.cluster.hostname.edu
    User myusername
    IdentityFile ~/.ssh/id_ed25519
    ControlMaster auto
    ControlPath ~/.ssh/control-%r@%h:%p
    ControlPersist 10m
```

**~/.config/slurm_monitor/config.json:**
```json
{
  "remote_host": "my-cluster",
  "ssh_timeout": 15,
  "refresh_interval": 5
}
```

## Project-Specific Log Paths

Different projects with different log directory structures:

```json
{
  "remote_host": "hpc.example.edu",
  "log_paths": {
    "default_pattern": "{work_dir}/logs/{job_id}.out",
    "specific_projects": {
      "ml_training": "{work_dir}/experiments/logs/train_{job_id}.log",
      "simulations": "{work_dir}/sim_output/job_{job_id}/stdout.txt",
      "preprocessing": "{work_dir}/data/logs/{job_id}.out"
    }
  }
}
```

**How it works:**
- If job work_dir contains "ml_training", uses that pattern
- If job work_dir contains "simulations", uses that pattern
- Otherwise, uses default pattern

## Complex Directory Structure

For complex nested project structures:

```json
{
  "remote_host": "supercomputer.edu",
  "ssh_timeout": 20,
  "refresh_interval": 3,
  "log_paths": {
    "default_pattern": "{work_dir}/slurm_logs/{job_id}.out",
    "specific_projects": {
      "deep_learning": "{work_dir}/runs/{project_name}/logs/{job_id}.log",
      "molecular_dynamics": "{work_dir}/trajectories/job_{job_id}/output.log",
      "genomics": "{work_dir}/analysis/logs/slurm-{job_id}.out",
      "climate_model": "{work_dir}/model_runs/{job_id}/stdout.txt"
    }
  }
}
```

## High-Frequency Monitoring

For users who want very frequent updates:

```json
{
  "remote_host": "fast-cluster.edu",
  "ssh_timeout": 5,
  "refresh_interval": 1,
  "log_paths": {
    "default_pattern": "{work_dir}/logs/{job_id}.out"
  }
}
```

**Note:** More frequent updates increase load. Use ControlMaster in SSH config for best performance.

## Slow Network Configuration

For slow or unreliable networks:

```json
{
  "remote_host": "remote-cluster.edu",
  "ssh_timeout": 30,
  "refresh_interval": 10,
  "log_paths": {
    "default_pattern": "{work_dir}/logs/{job_id}.out"
  }
}
```

## Multiple Clusters

You can create different config files for different clusters:

**~/.config/slurm_monitor/cluster1.json:**
```json
{
  "remote_host": "cluster1.university.edu",
  "log_paths": {
    "default_pattern": "{work_dir}/output/{job_id}.log"
  }
}
```

**~/.config/slurm_monitor/cluster2.json:**
```json
{
  "remote_host": "cluster2.university.edu",
  "log_paths": {
    "default_pattern": "{work_dir}/logs/slurm-{job_id}.out"
  }
}
```

Then specify which config to use when running the app (future feature).

## Token Reference

Available tokens for log path patterns:

- `{job_id}` - The Slurm job ID (e.g., "12345")
- `{work_dir}` - The job's working directory (from Slurm)
- `{project_name}` - Project name (auto-detected or manually specified)

### Examples:

```json
{
  "log_paths": {
    "default_pattern": "{work_dir}/logs/{job_id}.out",
    "specific_projects": {
      "my_project": "{work_dir}/{project_name}/output/job_{job_id}.log"
    }
  }
}
```

If a job has:
- `job_id`: "12345"
- `work_dir`: "/home/user/my_project/run1"
- Auto-detected project: "my_project"

Result: `/home/user/my_project/run1/my_project/output/job_12345.log`

## Common Patterns

### Standard Slurm Default
```json
"default_pattern": "{work_dir}/slurm-{job_id}.out"
```

### Logs Subdirectory
```json
"default_pattern": "{work_dir}/logs/{job_id}.out"
```

### Dated Logs
```json
"default_pattern": "{work_dir}/logs/$(date +%Y%m%d)/{job_id}.log"
```

### Job Name in Filename
```json
"default_pattern": "{work_dir}/logs/{job_name}_{job_id}.out"
```

Note: `{job_name}` token is not yet implemented but can be added if needed.

## Troubleshooting

### Logs Not Found

If you see "Cannot resolve log path" errors:

1. Check that your log path pattern matches where Slurm actually writes logs
2. Verify the tokens are correct
3. Test manually: `ssh cluster "ls /path/to/logs"`

### Wrong Project Detected

If the wrong project pattern is being used:

1. Check that your project names in config match directory names
2. Project detection is substring-based: "ml_project" matches "/home/user/ml_project/exp1"
3. Use more specific project names to avoid conflicts

### Performance Issues

If the app is slow:

1. Increase `refresh_interval` (less frequent updates)
2. Increase `ssh_timeout` if seeing timeout errors
3. Set up SSH ControlMaster (see SSH Setup in README)
4. Check network latency to cluster

## Best Practices

1. **Use SSH Config:** Define host aliases with ControlMaster for best performance
2. **Start Simple:** Begin with default pattern, add project-specific patterns as needed
3. **Test Patterns:** Verify log paths work before relying on them
4. **Document Projects:** Add comments (future feature) to config for team use
5. **Version Control:** Keep config.example.json in your project repos for team consistency
