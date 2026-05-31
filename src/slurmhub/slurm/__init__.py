"""Slurm command layer: SSH transport, command parsers, and demo fixtures.

Low-level modules that run Slurm commands over SSH and parse their output. This
layer depends only on :mod:`slurmhub.config`; the higher-level aggregation that
composes it lives in :mod:`slurmhub.core`.
"""
