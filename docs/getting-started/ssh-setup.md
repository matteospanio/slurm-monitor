# SSH connection setup

`slurm-monitor` uses [paramiko](https://www.paramiko.org/) (a pure-Python SSH library)
to talk to the cluster. Everything you can do with the regular `ssh` command — key
auth, password auth, jump hosts, agent forwarding, host aliases — works here too. The
recommended setup is **passwordless key authentication via an SSH config alias**,
because it lets the app reuse a single SSH connection across all the Slurm commands
it issues.

## Generate an SSH key

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

Press Enter at each prompt to accept the defaults. You can optionally set a
passphrase; if you do, run `ssh-add` so the key is unlocked once per login session.

## Copy your public key to the cluster

```bash
ssh-copy-id your-username@login.cluster.example.org
```

You will be prompted for your cluster password one last time. After this, key-based
login should work:

```bash
ssh your-username@login.cluster.example.org 'squeue --me'
```

## Add a host alias (strongly recommended)

Open or create `~/.ssh/config` and add:

```text
Host mycluster
    HostName       login.cluster.example.org
    User           your-username
    IdentityFile   ~/.ssh/id_ed25519
    Port           22

    # ControlMaster greatly reduces the per-command SSH overhead.
    # It opens one underlying TCP connection per host and reuses it.
    ControlMaster  auto
    ControlPath    ~/.ssh/control-%r@%h:%p
    ControlPersist 10m
```

`slurm-monitor` automatically reads `~/.ssh/config` and resolves hostnames, usernames,
ports, identity files, and `ProxyCommand` entries. Once the alias works:

```bash
ssh mycluster 'echo ok'
```

you can reference it in `config.toml` as simply:

```toml
[profiles.cluster]
host = "mycluster"
```

## Connecting through a bastion / jump host

The cleanest approach is SSH's native `ProxyJump`:

```text
Host bastion
    HostName  bastion.example.org
    User      your-username

Host mycluster
    HostName  login.cluster.example.org
    User      your-username
    ProxyJump bastion
```

Alternatively, declare the jump host directly in your `slurm-monitor` config:

```toml
[profiles.cluster]
host = "login.cluster.example.org"
ssh.username  = "your-username"
ssh.jump_host = "bastion.example.org"
```

## Password authentication

If you cannot use keys, leave the password fields empty in the config — the app will
detect the auth failure on the first refresh and pop up an interactive password
prompt. The password is held in memory only — it is never written to disk. You get up
to three attempts before the app stops re-prompting.

## Verifying the cluster side

Before launching the TUI, confirm that the basic Slurm commands respond:

```bash
ssh mycluster 'squeue --me'           # should list (or empty) your jobs
ssh mycluster 'sinfo -h -o "%R|%D"'   # should list partitions
ssh mycluster 'sacct -X -n | head -5' # should list recent history
```

If any of these hang or fail, fix the SSH or Slurm side first; the TUI will surface
the same errors but the diagnostics are easier to read from the shell.
