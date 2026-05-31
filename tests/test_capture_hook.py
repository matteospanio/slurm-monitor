"""Integration tests for the refresh-cycle capture hook in SlurmhubApp."""

import pytest

from slurmhub.tui.app import SlurmhubApp
from slurmhub.config import AppConfig, ProfileConfig, SSHConfig
from slurmhub.db.engine import Database, _run_migrations, make_engine
from slurmhub.db.models import UsageSnapshot
from slurmhub.db.repository import Repository
from slurmhub.slurm.demo_data import DEMO_HOST, DEMO_USERNAME


def _demo_config() -> AppConfig:
    profile = ProfileConfig(
        name="demo", ssh=SSHConfig(host=DEMO_HOST, username=DEMO_USERNAME)
    )
    return AppConfig(profiles={"demo": profile})


def fresh_db() -> Database:
    engine = make_engine("sqlite://", in_memory=True)
    _run_migrations(engine)
    return Database(engine)


@pytest.mark.asyncio
async def test_refresh_writes_snapshots_for_running_jobs():
    db = fresh_db()
    app = SlurmhubApp(config=_demo_config(), demo=True, database=db)
    repo = Repository()
    async with app.run_test() as pilot:
        await pilot.pause(0.6)  # let the background refresh worker run
        with db.session() as s:
            runs = repo.query_runs(s)
            # Active + historical demo jobs are all recorded.
            assert len(runs) >= 5
            # The running demo jobs accrue snapshots; terminal ones do not.
            running_ids = {r.job_id for r in runs if r.state == "RUNNING"}
            assert running_ids
            snap_job_pks = {row.job_pk for row in s.query(UsageSnapshot).all()}
            running_pks = {r.pk for r in runs if r.state == "RUNNING"}
            terminal_pks = {
                r.pk for r in runs if r.state in ("COMPLETED", "FAILED", "CANCELLED")
            }
            assert snap_job_pks & running_pks  # running jobs snapshotted
            assert not (snap_job_pks & terminal_pks)  # terminal jobs not


@pytest.mark.asyncio
async def test_db_failure_does_not_break_refresh(monkeypatch):
    db = fresh_db()
    app = SlurmhubApp(config=_demo_config(), demo=True, database=db)

    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(app.repository, "capture_refresh", boom)

    async with app.run_test() as pilot:
        await pilot.pause(0.6)
        # Monitoring still works despite the capture failure.
        tab = app._profile_tabs["demo"]
        assert tab.jobs  # jobs were fetched and applied


@pytest.mark.asyncio
async def test_database_none_skips_capture():
    app = SlurmhubApp(config=_demo_config(), demo=True, database=None)
    async with app.run_test() as pilot:
        await pilot.pause(0.4)
        assert app.repository is None
        assert app._profile_tabs["demo"].jobs  # still monitors
