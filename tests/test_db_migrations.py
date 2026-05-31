"""Tests for Alembic migration setup, idempotency, and packaging."""

import importlib
from pathlib import Path

from sqlalchemy import inspect

from slurmhub.config import DatabaseConfig
from slurmhub.db.engine import _run_migrations, make_engine, open_database


def test_upgrade_creates_all_tables():
    engine = make_engine("sqlite://", in_memory=True)
    _run_migrations(engine)
    tables = set(inspect(engine).get_table_names())
    assert {"jobs", "usage_snapshots", "favourites", "alembic_version"} <= tables


def test_upgrade_is_idempotent():
    engine = make_engine("sqlite://", in_memory=True)
    _run_migrations(engine)
    # Running again must be a harmless no-op (already at head).
    _run_migrations(engine)
    with engine.connect() as conn:
        from sqlalchemy import text

        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "0002"


def test_initial_revision_module_is_packaged():
    # Guards that the migration ships as importable package data in the wheel;
    # the runtime upgrade path depends on the versions/*.py being present.
    mod = importlib.import_module("slurmhub.db.alembic.versions")
    versions_dir = Path(mod.__file__).parent
    assert (versions_dir / "0001_initial.py").exists()
    assert (versions_dir / "0002_snapshot_cpu_util.py").exists()


def test_open_database_creates_file_and_dir(tmp_path):
    db_path = tmp_path / "nested" / "dir" / "jobs.db"
    cfg = DatabaseConfig(enabled=True, path=str(db_path))
    db = open_database(cfg)
    assert db is not None
    assert db_path.exists()
    db.close()


def test_open_database_disabled_returns_none(tmp_path):
    cfg = DatabaseConfig(enabled=False, path=str(tmp_path / "jobs.db"))
    assert open_database(cfg) is None
    assert not (tmp_path / "jobs.db").exists()
