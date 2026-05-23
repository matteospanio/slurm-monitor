# Troubleshooting

## Connection errors

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Red dot, "SSH connection to … failed" | Host unreachable, VPN down | Verify `ssh <host> echo ok` from a shell. |
| Red dot, "SSH authentication failed" | No agent, wrong key, locked key | Run `ssh-add ~/.ssh/id_ed25519`, or let the password prompt take over. |
| Red dot, "timed out" | Network slow / wrong host | Increase `ssh_timeout`. |
| Yellow ⚠ next to a green dot | Auxiliary call (`sinfo`, queue stats, pending details) failed | Main job list is fine. Open the notification or run the command manually. |

## Empty job table

- Confirm `ssh <host> 'squeue --me'` returns rows from the shell.
- Check that the `--me` flag is recognized by your Slurm version (Slurm ≥ 17.11).

## "No matches" in the log viewer

The buffer holds the last 20 000 lines. Searches over older lines return no matches —
scroll the log back or restart the viewer to refill the buffer.

## Logs not opening from the detail screen

- Press `Enter` first to make sure the detail screen has finished its
  `scontrol show job` call (the StdOut / StdErr lines must be populated).
- If `scontrol` doesn't return a path (rare, very old jobs), check that
  `log.default_pattern` in your config matches your cluster's convention.

## GPU bars are missing for a GPU job

- Some sites disable `srun --overlap` for accounting. The Allocated count from
  `scontrol` still shows; the per-GPU utilisation bars will not.
- Test with `ssh <host> "srun --jobid=<jobid> --overlap nvidia-smi"`.

## Clipboard (yank) not working

- The terminal needs OSC 52 support. iTerm2, WezTerm, kitty, and Alacritty work out
  of the box. In tmux, add `set -g set-clipboard on`.
- The notification will say "Clipboard unavailable — …" and still print the value
  so you can copy it manually.

## Performance

- Increase `refresh_interval` if the cluster is slow.
- Configure `ControlMaster auto` in `~/.ssh/config` — paramiko ignores the directive
  at the protocol level, but it speeds up any external `ssh` calls you make.

## Reproducing UI bugs without a cluster

```{tip}
Use `slurmhub --demo` to exercise the UI against built-in fixture data. If a visual
bug reproduces in demo mode, the bug is in the TUI code — not in your cluster or
your config. Attach the reproduction steps (and the terminal you're using) to your
bug report.
```
