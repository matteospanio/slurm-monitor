"""Tests for the per-profile snapshot cache (framework-agnostic)."""

import json

from slurmhub.queue_stats import ClusterQueueStats
from slurmhub.sinfo_parser import ClusterCapacity, NodeStats, PartitionStats
from slurmhub.snapshot_cache import CachedSnapshot, SnapshotCache
from slurmhub.squeue_parser import SlurmJob


def test_round_trip(tmp_path):
    cache = SnapshotCache(tmp_path)
    snap = CachedSnapshot(
        profile_name="prod",
        cached_at="2026-05-31 14:00:00",
        jobs=[SlurmJob(job_id="1", name="train", state="RUNNING", time="00:05", num_cpus=4)],
        queue_stats=ClusterQueueStats(total_running=2, total_pending=1),
        cluster_capacity=ClusterCapacity(cpus_used=10, cpus_total=20),
        partitions=[PartitionStats(name="gpu", nodes_total=3)],
        nodes=[NodeStats(name="n1", state="idle")],
    )
    cache.save(snap)

    loaded = cache.load("prod")
    assert loaded is not None
    assert loaded.cached_at == "2026-05-31 14:00:00"
    assert loaded.jobs[0].job_id == "1" and loaded.jobs[0].num_cpus == 4
    assert loaded.queue_stats.total_running == 2
    assert loaded.cluster_capacity.cpus_total == 20
    assert loaded.partitions[0].name == "gpu"
    assert loaded.nodes[0].name == "n1"


def test_missing_returns_none(tmp_path):
    assert SnapshotCache(tmp_path).load("nope") is None


def test_corrupt_returns_none(tmp_path):
    cache = SnapshotCache(tmp_path)
    cache.cache_dir.mkdir(parents=True, exist_ok=True)
    cache.path("p").write_text("{ not valid json")
    assert cache.load("p") is None


def test_unknown_keys_are_ignored(tmp_path):
    cache = SnapshotCache(tmp_path)
    cache.cache_dir.mkdir(parents=True, exist_ok=True)
    cache.path("p").write_text(
        json.dumps(
            {
                "profile_name": "p",
                "cached_at": "t",
                "jobs": [
                    {"job_id": "1", "name": "a", "state": "RUNNING",
                     "time": "0:01", "from_a_future_version": 123}
                ],
            }
        )
    )
    loaded = cache.load("p")
    assert loaded is not None
    assert loaded.jobs[0].job_id == "1"


def test_profile_name_is_slugged(tmp_path):
    cache = SnapshotCache(tmp_path)
    # A name with path-unfriendly characters still yields a single safe file.
    p = cache.path("my cluster/01")
    assert p.parent == tmp_path
    assert "/" not in p.name and " " not in p.name
