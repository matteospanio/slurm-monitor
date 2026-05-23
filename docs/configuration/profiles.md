# Profiles

Each `[profiles.<name>]` block defines one cluster connection. Profiles are independent:
each has its own SSH client, refresh worker, sacct/sinfo caches, and filter/sort state.

## Single profile

```toml
[profiles.mycluster]
host = "mycluster"   # resolved via ~/.ssh/config
```

With a single profile, the UI shows no tab bar — the connection status header and the
job table take up the full screen.

## Multiple profiles — tabs

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

When more than one profile is configured, the UI grows a tab bar. Press `h` / `l` to
switch tabs without leaving the keyboard. Per-tab state that is preserved when
switching:

- **State filter** (`1`/`2`/`3`/`4`/`0`)
- **Name / ID search** (`/`)
- **Sort mode** (`s`)
- **Cursor position**

## Running a subset of configured profiles

```bash
slurmhub --profile dei            # only the 'dei' profile
slurmhub --list-profiles          # list and exit
```

## Ad-hoc profile without a config

```bash
slurmhub --host login.cluster.example.org
```

This creates an in-memory profile named `default` and starts the app against it. No
file on disk is created or modified.

## Overrides via `[defaults]`

Anything under `[defaults]` is treated as the base layer. Individual profiles
selectively override fields:

```toml
[defaults]
ssh_timeout = 15
[defaults.ssh]
username = "shared-user"
key_filename = "~/.ssh/id_shared"

[profiles.alpha]
host = "alpha.cluster.example.edu"
# inherits username, key_filename, ssh_timeout

[profiles.beta]
host = "beta.cluster.example.edu"
ssh.username = "beta-user"   # overrides 'shared-user' just for this profile
ssh_timeout = 30             # overrides 15
```

The merge is shallow per section, except for `log.specific_projects` (which is
deep-merged so per-profile entries are added to the defaults rather than replacing
them).
