"""PySide6 desktop GUI for slurmhub.

This package contains *only* the view layer. All cluster I/O, parsing,
persistence, and configuration live in the framework-agnostic modules under
``slurmhub`` (``ssh_wrapper``, the ``*_parser`` modules, ``job_aggregator``,
``queue_stats``, ``db``, ``config``) and are reused verbatim. Nothing here
imports :mod:`textual`, so launching the GUI never pulls in the TUI.
"""
