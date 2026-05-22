# Examples

Copy-paste configurations for common situations.

## Minimal — one cluster, all defaults

```toml
[profiles.mycluster]
host = "mycluster"   # resolved via ~/.ssh/config
```

## Multi-cluster — appears as tabs

```toml
[defaults]
refresh_interval = 5

[profiles.dei]
host = "dei.login"

[profiles.cineca]
host         = "login.cineca.it"
ssh.username = "auser"
ssh.key_filename = "~/.ssh/id_cineca"
refresh_interval = 10              # poll less often on remote/slow clusters

[profiles.hpc]
host          = "hpc.university.edu"
ssh.jump_host = "bastion.university.edu"
```

## Project-specific log patterns

```toml
[profiles.mycluster]
host = "mycluster"
log.default_pattern = "{work_dir}/logs/{job_id}.out"
log.specific_projects.ml_training   = "{work_dir}/experiments/{job_id}.log"
log.specific_projects.simulations   = "{work_dir}/sim_output/job_{job_id}/stdout.txt"
log.specific_projects.preprocessing = "{work_dir}/data/logs/{job_id}.out"
```

## Complex nested directories

```toml
[profiles.supercomputer]
host = "supercomputer.edu"
ssh_timeout = 20
refresh_interval = 3

log.default_pattern = "{work_dir}/slurm_logs/{job_id}.out"
log.specific_projects.deep_learning       = "{work_dir}/runs/{project_name}/logs/{job_id}.log"
log.specific_projects.molecular_dynamics  = "{work_dir}/trajectories/job_{job_id}/output.log"
log.specific_projects.genomics            = "{work_dir}/analysis/logs/slurm-{job_id}.out"
log.specific_projects.climate_model       = "{work_dir}/model_runs/{job_id}/stdout.txt"
```

## High-frequency monitoring

```toml
[defaults]
ssh_timeout = 5
refresh_interval = 2

[profiles.fast]
host = "fast-cluster.edu"
```

```{note}
More frequent updates increase load on both your machine and the cluster login node.
Configure `ControlMaster auto` in `~/.ssh/config` for best performance — paramiko
ignores the directive itself, but any external `ssh` calls you make (e.g. for
debugging) will benefit.
```

## Slow / unreliable network

```toml
[defaults]
ssh_timeout = 30
refresh_interval = 15
sacct_refresh_interval = 300

[profiles.remote]
host = "remote-cluster.edu"
```

## GPU-heavy workload

When most of your jobs use GPUs and you want richer GPU telemetry, ensure the cluster
allows `srun --jobid=<id> --overlap nvidia-smi` from a login node — the detail screen
uses that to fill in per-GPU utilisation bars. No client-side configuration is
required; the call is attempted whenever a job declares GPUs in its `ReqTRES`.

## Legacy JSON (still supported)

```json
{
  "remote_host": "cluster.example.edu",
  "ssh_timeout": 10,
  "refresh_interval": 5,
  "log_paths": {
    "default_pattern": "{work_dir}/logs/{job_id}.out",
    "specific_projects": {
      "ml_project": "{work_dir}/ml/logs/{job_id}.log"
    }
  }
}
```

The loader converts this to a single `default` profile. New deployments should start
from TOML.
