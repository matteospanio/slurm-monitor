"""Engine, session, and migration management for the history database.

A single SQLite file at ``~/.config/slurmhub/jobs.db`` (configurable) backs the
feature. The engine is created with ``check_same_thread=False`` and WAL mode so
the refresh worker (writer) and the history screen (reader) can run on separate
Textual worker threads without ``database is locked`` errors.

Schema is brought to head by Alembic at startup via :func:`_run_migrations`,
sharing the live connection so the *same* database is migrated (this matters for
the in-memory demo database, where a fresh engine would migrate a throwaway DB).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

if TYPE_CHECKING:
    from slurmhub.config import DatabaseConfig

_ALEMBIC_DIR = Path(__file__).parent / "alembic"


def _install_pragmas(engine: Engine) -> None:
    """Set per-connection SQLite pragmas (WAL, foreign keys, busy timeout)."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        # foreign_keys is load-bearing: retention relies on ON DELETE CASCADE.
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


def make_engine(url: str, *, in_memory: bool = False) -> Engine:
    """Create a SQLite engine wired for multi-threaded TUI use."""
    connect_args = {"check_same_thread": False}
    if in_memory:
        # One shared connection so every worker thread sees the same in-memory
        # database (the default SingletonThreadPool would give each thread its
        # own empty DB).
        engine = create_engine(
            url, connect_args=connect_args, poolclass=StaticPool, future=True
        )
    else:
        engine = create_engine(url, connect_args=connect_args, future=True)
    _install_pragmas(engine)
    return engine


def resolve_db_path(db_cfg: "DatabaseConfig") -> Path:
    """Resolve the on-disk database path, honoring an explicit override."""
    from slurmhub.config import ConfigLoader

    if db_cfg.path:
        return Path(db_cfg.path).expanduser()
    return ConfigLoader.get_config_dir() / "jobs.db"


def _run_migrations(engine: Engine) -> None:
    """Upgrade the database to the latest Alembic revision (idempotent).

    Alembic is imported lazily so a user who disables persistence never pays
    the import cost. The live connection is injected via ``config.attributes``
    so the in-memory demo database is migrated in place.
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(_ALEMBIC_DIR))
    with engine.connect() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")


class Database:
    """Owns the engine + session factory and the lifecycle of the DB file."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self._session_factory = sessionmaker(
            bind=engine, expire_on_commit=False, future=True
        )
        self._closed = False

    @property
    def enabled(self) -> bool:
        return not self._closed

    def session(self) -> Session:
        """Return a new session (use as a context manager per operation)."""
        return self._session_factory()

    def close(self) -> None:
        """Dispose of the engine. Idempotent and safe to call on exit."""
        if self._closed:
            return
        self._closed = True
        try:
            self.engine.dispose()
        except Exception:
            pass


def open_database(db_cfg: "DatabaseConfig") -> Optional[Database]:
    """Open (creating + migrating if needed) the configured database.

    Returns ``None`` when persistence is disabled. Raises on migration/IO
    failure so the caller (cli.py) can degrade to "persistence off" cleanly.
    """
    if not db_cfg.enabled:
        return None

    path = resolve_db_path(db_cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = make_engine(f"sqlite:///{path}")
    _run_migrations(engine)
    return Database(engine)


def open_demo_database() -> Database:
    """Open a throwaway in-memory database, migrated and seeded for --demo.

    Never touches ``~/.config``.
    """
    engine = make_engine("sqlite://", in_memory=True)
    _run_migrations(engine)
    db = Database(engine)
    from slurmhub.db.demo_seed import seed_demo_database

    seed_demo_database(db)
    return db
