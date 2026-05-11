"""Parser for `sinfo` output — cluster nodes, partitions, and capacity."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from slurm_monitor.ssh_wrapper import SSHClient

# Slurm appends one of these characters to a state to signal additional info
# (e.g. ``mixed*`` = mixed + non-responding). Strip them before matching.
_STATE_SUFFIXES = "*~%$#@!+"

# Match GRES strings used by sinfo: ``gpu:l40s:4``, ``gpu:4``, ``gpu:a100:8(IDX:0-7)``.
_GRES_GPU_RE = re.compile(r"gpu(?::([\w-]+))?:(\d+)")


@dataclass
class PartitionStats:
    """Aggregate stats for a single partition."""

    name: str
    nodes_total: int = 0
    nodes_idle: int = 0
    nodes_mixed: int = 0
    nodes_alloc: int = 0
    nodes_down: int = 0
    cpus_alloc: int = 0
    cpus_idle: int = 0
    cpus_total: int = 0
    gpus_total: int = 0
    gpus_used: int = 0
    mem_total_mb: int = 0
    available: bool = True


@dataclass
class NodeStats:
    """State of a single compute node."""

    name: str
    partition: str = ""
    state: str = ""
    cpus_alloc: int = 0
    cpus_total: int = 0
    mem_free_mb: int = 0
    mem_total_mb: int = 0
    gpus_total: int = 0
    gpus_used: int = 0
    gres_raw: str = ""
    reason: str = ""


@dataclass
class ClusterCapacity:
    """Top-of-dashboard aggregate, derived from the node list."""

    nodes_up: int = 0
    nodes_down: int = 0
    nodes_drain: int = 0
    cpus_used: int = 0
    cpus_total: int = 0
    gpus_used: int = 0
    gpus_total: int = 0
    mem_used_mb: int = 0
    mem_total_mb: int = 0
    fetched_at: str = ""

    @property
    def cpu_percentage(self) -> float:
        return round(self.cpus_used / self.cpus_total * 100, 1) if self.cpus_total else 0.0

    @property
    def gpu_percentage(self) -> float:
        return round(self.gpus_used / self.gpus_total * 100, 1) if self.gpus_total else 0.0

    @property
    def mem_percentage(self) -> float:
        return round(self.mem_used_mb / self.mem_total_mb * 100, 1) if self.mem_total_mb else 0.0


def normalize_state(raw: str) -> str:
    """Strip Slurm state suffixes (``*``, ``~``, ``%`` …) and lowercase."""
    if not raw:
        return ""
    stripped = raw.rstrip(_STATE_SUFFIXES)
    return stripped.lower()


def parse_cpu_aiot(field_value: str) -> tuple[int, int, int, int]:
    """Parse an ``%C`` Allocated/Idle/Other/Total string like ``32/96/0/128``."""
    parts = field_value.split("/")
    if len(parts) != 4:
        return (0, 0, 0, 0)
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
    except ValueError:
        return (0, 0, 0, 0)


def parse_gres_total(gres: str) -> int:
    """Count total GPUs declared in a ``%G`` gres string.

    Examples:
        ``(null)`` -> 0
        ``gpu:4`` -> 4
        ``gpu:l40s:4`` -> 4
        ``gpu:a100:8(IDX:0-7)`` -> 8
        ``gpu:l40s:2,gpu:a100:4`` -> 6
    """
    if not gres or gres.strip().lower() in ("(null)", "n/a", "", "-"):
        return 0
    total = 0
    for match in _GRES_GPU_RE.finditer(gres):
        try:
            total += int(match.group(2))
        except (TypeError, ValueError):
            continue
    return total


def parse_gres_used(gres_used: str) -> int:
    """Count GPUs currently allocated from a ``GresUsed`` style string.

    sinfo's ``%G`` only describes declared resources; allocation comes from
    other fields. This helper is reused if we ever wire ``%E`` / ``GresUsed``.
    The grammar is similar to declared gres.
    """
    return parse_gres_total(gres_used)


def parse_mem_mb(field_value: str) -> int:
    """Parse a memory value that sinfo reports in megabytes."""
    if not field_value:
        return 0
    value = field_value.strip()
    if value in ("N/A", "n/a", "-", ""):
        return 0
    try:
        return int(value)
    except ValueError:
        # Some sites emit suffixes like '512000M' — strip a trailing letter.
        if value[-1].isalpha():
            try:
                return int(value[:-1])
            except ValueError:
                return 0
        return 0


def parse_nodes(output: str) -> list[NodeStats]:
    """Parse the per-node ``sinfo -N`` output.

    Expected format (pipe-delimited, no header):
        Name|Partition|State|CPUs(A/I/O/T)|FreeMem|RealMemory|Gres|Reason
    """
    nodes: list[NodeStats] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) < 7:
            continue
        name, partition, state_raw, cpus_aiot, free_mem, total_mem, gres = parts[:7]
        reason = parts[7] if len(parts) >= 8 else ""

        alloc, _idle, _other, total_cpus = parse_cpu_aiot(cpus_aiot)
        node = NodeStats(
            name=name.strip(),
            partition=partition.strip(),
            state=normalize_state(state_raw),
            cpus_alloc=alloc,
            cpus_total=total_cpus,
            mem_free_mb=parse_mem_mb(free_mem),
            mem_total_mb=parse_mem_mb(total_mem),
            gpus_total=parse_gres_total(gres),
            gres_raw=gres.strip(),
            reason=reason.strip() if reason.strip().lower() not in ("(null)", "none", "") else "",
        )
        # GPU "used" is unknown from `%G` alone; treat fully-allocated nodes
        # as using all their GPUs and idle nodes as using none. Mixed nodes
        # are conservatively reported as used == declared (Slurm doesn't
        # expose per-job GPU counts cheaply through sinfo).
        if node.state in ("allocated", "alloc"):
            node.gpus_used = node.gpus_total
        elif node.state in ("mixed",):
            node.gpus_used = node.gpus_total
        else:
            node.gpus_used = 0
        nodes.append(node)
    return nodes


def parse_partitions(output: str, nodes: list[NodeStats]) -> list[PartitionStats]:
    """Parse the per-partition ``sinfo`` output and merge per-node aggregates.

    Per-partition format:
        Name|Nodes|CPUs(A/I/O/T)|Gres|Mem|Avail
    """
    partitions: dict[str, PartitionStats] = {}
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) < 6:
            continue
        name, nodes_total, cpus_aiot, gres, mem_total, avail = parts[:6]
        alloc, idle, _other, total_cpus = parse_cpu_aiot(cpus_aiot)
        try:
            n_total = int(nodes_total)
        except ValueError:
            n_total = 0
        partitions[name.strip()] = PartitionStats(
            name=name.strip(),
            nodes_total=n_total,
            cpus_alloc=alloc,
            cpus_idle=idle,
            cpus_total=total_cpus,
            gpus_total=parse_gres_total(gres),
            mem_total_mb=parse_mem_mb(mem_total),
            available=avail.strip().lower() == "up",
        )

    # Walk the node list to fill in per-partition state counts and GPU usage.
    for node in nodes:
        # A node can belong to multiple partitions (comma-separated).
        for part_name in (p.strip() for p in node.partition.split(",")):
            ps = partitions.get(part_name)
            if ps is None:
                continue
            state = node.state
            if state == "idle":
                ps.nodes_idle += 1
            elif state == "mixed":
                ps.nodes_mixed += 1
            elif state in ("allocated", "alloc"):
                ps.nodes_alloc += 1
            elif state in ("down", "drain", "drained", "draining", "fail", "failing"):
                ps.nodes_down += 1
            ps.gpus_used += node.gpus_used

    # Cap derived counts so a misaligned partition definition doesn't show
    # more used GPUs than the partition declares.
    for ps in partitions.values():
        if ps.gpus_total and ps.gpus_used > ps.gpus_total:
            ps.gpus_used = ps.gpus_total

    return list(partitions.values())


def aggregate_capacity(nodes: list[NodeStats]) -> ClusterCapacity:
    """Roll node-level stats up into a single ClusterCapacity."""
    cap = ClusterCapacity()
    for node in nodes:
        state = node.state
        if state in ("down", "fail", "failing"):
            cap.nodes_down += 1
        elif state in ("drain", "drained", "draining"):
            cap.nodes_drain += 1
            # Drained nodes are technically still reachable; count them as
            # "up" for capacity purposes so we don't double-count.
            cap.nodes_up += 1
        else:
            cap.nodes_up += 1

        cap.cpus_used += node.cpus_alloc
        cap.cpus_total += node.cpus_total
        cap.gpus_used += node.gpus_used
        cap.gpus_total += node.gpus_total
        cap.mem_total_mb += node.mem_total_mb
        # Memory "used" is total - free, when free is reported.
        if node.mem_total_mb:
            used = max(node.mem_total_mb - node.mem_free_mb, 0)
            cap.mem_used_mb += used
    return cap


# Format strings kept as module-level constants so tests can reuse them.
SINFO_PARTITION_FMT = "%R|%D|%C|%G|%m|%a"
SINFO_NODE_FMT = "%N|%R|%T|%C|%e|%m|%G|%E"


def fetch_sinfo(
    client: SSHClient, timeout: int = 10
) -> tuple[ClusterCapacity, list[PartitionStats], list[NodeStats]]:
    """Fetch cluster nodes + partitions and roll up into a ClusterCapacity.

    Runs two ``sinfo`` calls (per-partition and per-node) and stitches them
    together. Failures bubble up as :class:`SSHConnectionError` /
    :class:`SSHTimeoutError` so the caller can decide how to handle them.
    """
    nodes_out = client.execute(
        f'sinfo -h -N -o "{SINFO_NODE_FMT}"', timeout
    )
    nodes = parse_nodes(nodes_out)

    partitions_out = client.execute(
        f'sinfo -h -o "{SINFO_PARTITION_FMT}"', timeout
    )
    partitions = parse_partitions(partitions_out, nodes)

    capacity = aggregate_capacity(nodes)
    capacity.fetched_at = datetime.now().strftime("%H:%M:%S")
    return capacity, partitions, nodes
