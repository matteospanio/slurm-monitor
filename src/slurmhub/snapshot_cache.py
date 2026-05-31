"""Per-profile snapshot cache for instant startup display.

Persists the last successful fetch (jobs + queue stats + cluster capacity /
partitions / nodes) to a small JSON file per profile, so the app can paint the
*last-known* status immediately on launch while it fetches fresh data. The
cached view is read-only — callers must not allow state-changing actions
(scancel/requeue/…) on cached jobs, since their real state is unknown until the
first live refresh lands.

Framework-agnostic: it (de)serialises the plain core dataclasses and never
imports Qt. Any read/write error degrades to "no cache" rather than raising, so
caching can never block the app.
"""

import dataclasses
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Type, TypeVar

from slurmhub.queue_stats import ClusterQueueStats
from slurmhub.sinfo_parser import ClusterCapacity, NodeStats, PartitionStats
from slurmhub.squeue_parser import SlurmJob

T = TypeVar("T")


@dataclass
class CachedSnapshot:
    """A point-in-time copy of one profile's displayable state."""

    profile_name: str
    cached_at: str  # display string, e.g. "2026-05-31 14:07:50"
    jobs: list[SlurmJob] = field(default_factory=list)
    queue_stats: Optional[ClusterQueueStats] = None
    cluster_capacity: Optional[ClusterCapacity] = None
    partitions: list[PartitionStats] = field(default_factory=list)
    nodes: list[NodeStats] = field(default_factory=list)


def _build(cls: Type[T], data: Optional[dict]) -> Optional[T]:
    """Reconstruct a dataclass from a dict, ignoring unknown keys."""
    if data is None:
        return None
    names = {f.name for f in dataclasses.fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in names})


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name) or "default"


class SnapshotCache:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = Path(cache_dir)

    def path(self, profile_name: str) -> Path:
        return self.cache_dir / f"{_slug(profile_name)}.json"

    def save(self, snapshot: CachedSnapshot) -> None:
        """Write the snapshot atomically; swallow any I/O error."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "profile_name": snapshot.profile_name,
                "cached_at": snapshot.cached_at,
                "jobs": [dataclasses.asdict(j) for j in snapshot.jobs],
                "queue_stats": dataclasses.asdict(snapshot.queue_stats)
                if snapshot.queue_stats is not None
                else None,
                "cluster_capacity": dataclasses.asdict(snapshot.cluster_capacity)
                if snapshot.cluster_capacity is not None
                else None,
                "partitions": [dataclasses.asdict(p) for p in snapshot.partitions],
                "nodes": [dataclasses.asdict(n) for n in snapshot.nodes],
            }
            target = self.path(snapshot.profile_name)
            tmp = target.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(tmp, target)
        except Exception:  # noqa: BLE001 — caching must never break the app
            pass

    def load(self, profile_name: str) -> Optional[CachedSnapshot]:
        """Return the cached snapshot, or None if missing/unreadable/stale-schema."""
        try:
            raw = self.path(profile_name).read_text(encoding="utf-8")
            data = json.loads(raw)
            return CachedSnapshot(
                profile_name=data.get("profile_name", profile_name),
                cached_at=data.get("cached_at", ""),
                jobs=[_build(SlurmJob, j) for j in data.get("jobs", [])],
                queue_stats=_build(ClusterQueueStats, data.get("queue_stats")),
                cluster_capacity=_build(ClusterCapacity, data.get("cluster_capacity")),
                partitions=[_build(PartitionStats, p) for p in data.get("partitions", [])],
                nodes=[_build(NodeStats, n) for n in data.get("nodes", [])],
            )
        except Exception:  # noqa: BLE001 — missing/corrupt/old cache → no cache
            return None
