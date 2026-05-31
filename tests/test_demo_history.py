"""Demo-mode database isolation + seeding tests."""

from slurmhub.db.engine import open_demo_database
from slurmhub.db.repository import Repository


def test_demo_database_is_seeded():
    db = open_demo_database()
    repo = Repository()
    with db.session() as s:
        runs = repo.query_runs(s)
        assert len(runs) >= 6
        favs = repo.query_runs(s, favourites_only=True)
        assert len(favs) >= 1
        # At least one favourite carries a note.
        assert any(f.note for f in favs)
        # Aggregates are computable from the seeded allocation data.
        tot = repo.aggregate_usage(s)
        assert tot.gpu_hours > 0
    db.close()


def test_demo_database_is_in_memory_and_resolves_no_path(monkeypatch):
    # The true isolation guarantee: the demo DB uses an in-memory engine and
    # never resolves an on-disk config path. Fail loudly if it ever tries.
    import slurmhub.db.engine as engine_mod

    def _boom(*a, **k):  # pragma: no cover - only runs on regression
        raise AssertionError("open_demo_database must not resolve a disk path")

    monkeypatch.setattr(engine_mod, "resolve_db_path", _boom)

    db = open_demo_database()
    try:
        assert str(db.engine.url) == "sqlite://"  # in-memory, no file
    finally:
        db.close()
