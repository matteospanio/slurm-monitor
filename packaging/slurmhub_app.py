"""PyInstaller entry point for the bundled desktop app.

Double-clicking the packaged binary runs with no CLI args, so ``cli.main``
launches the GUI by default. CLI flags still work when run from a terminal.
"""

from slurmhub.cli import main

if __name__ == "__main__":
    main()
