"""Tests for the sinfo parser and capacity aggregation."""

from unittest.mock import MagicMock

import pytest

from slurm_monitor.sinfo_parser import (
    ClusterCapacity,
    NodeStats,
    PartitionStats,
    SINFO_NODE_FMT,
    SINFO_PARTITION_FMT,
    aggregate_capacity,
    fetch_sinfo,
    normalize_state,
    parse_cpu_aiot,
    parse_gres_total,
    parse_mem_mb,
    parse_nodes,
    parse_partitions,
)


class TestNormalizeState:
    def test_strips_star_suffix(self):
        assert normalize_state("mixed*") == "mixed"

    def test_strips_tilde_suffix(self):
        assert normalize_state("idle~") == "idle"

    def test_strips_combined_suffixes(self):
        # "drained*~" can occur when a node is drained and non-responding
        assert normalize_state("drained*~") == "drained"

    def test_lowercases(self):
        assert normalize_state("ALLOCATED") == "allocated"

    def test_empty(self):
        assert normalize_state("") == ""


class TestParseCpuAiot:
    def test_standard(self):
        assert parse_cpu_aiot("32/96/0/128") == (32, 96, 0, 128)

    def test_malformed(self):
        assert parse_cpu_aiot("not/a/number/here") == (0, 0, 0, 0)

    def test_wrong_arity(self):
        assert parse_cpu_aiot("32/96") == (0, 0, 0, 0)

    def test_empty(self):
        assert parse_cpu_aiot("") == (0, 0, 0, 0)


class TestParseGresTotal:
    def test_null(self):
        assert parse_gres_total("(null)") == 0

    def test_empty_string(self):
        assert parse_gres_total("") == 0

    def test_dash(self):
        assert parse_gres_total("-") == 0

    def test_generic_count(self):
        assert parse_gres_total("gpu:4") == 4

    def test_typed_count(self):
        assert parse_gres_total("gpu:l40s:4") == 4

    def test_typed_count_with_idx(self):
        assert parse_gres_total("gpu:a100:8(IDX:0-7)") == 8

    def test_multiple_types(self):
        assert parse_gres_total("gpu:l40s:2,gpu:a100:4") == 6


class TestParseMemMb:
    def test_plain_int(self):
        assert parse_mem_mb("512000") == 512000

    def test_with_suffix(self):
        assert parse_mem_mb("512000M") == 512000

    def test_empty(self):
        assert parse_mem_mb("") == 0

    def test_na(self):
        assert parse_mem_mb("N/A") == 0


class TestParseNodes:
    def test_basic_idle_node(self):
        output = "gpu01|gpu|idle|0/32/0/32|256000|256000|gpu:l40s:4|"
        nodes = parse_nodes(output)
        assert len(nodes) == 1
        n = nodes[0]
        assert n.name == "gpu01"
        assert n.partition == "gpu"
        assert n.state == "idle"
        assert n.cpus_alloc == 0
        assert n.cpus_total == 32
        assert n.mem_free_mb == 256000
        assert n.mem_total_mb == 256000
        assert n.gpus_total == 4
        assert n.gpus_used == 0
        assert n.reason == ""

    def test_alloc_node_marks_gpus_used(self):
        output = "gpu02|gpu|allocated|32/0/0/32|10000|256000|gpu:l40s:4|"
        nodes = parse_nodes(output)
        assert nodes[0].gpus_used == 4

    def test_mixed_node_marks_gpus_used(self):
        output = "gpu03|gpu|mixed|16/16/0/32|128000|256000|gpu:a100:8|"
        n = parse_nodes(output)[0]
        assert n.state == "mixed"
        assert n.gpus_used == 8

    def test_drained_node_with_reason(self):
        output = "cpu04|cpu|drained|0/0/0/64|0|512000|(null)|maintenance"
        n = parse_nodes(output)[0]
        assert n.state == "drained"
        assert n.reason == "maintenance"
        assert n.gpus_total == 0
        assert n.gpus_used == 0

    def test_down_node(self):
        output = "cpu05|cpu|down*|0/0/0/64|0|512000|(null)|not responding"
        n = parse_nodes(output)[0]
        assert n.state == "down"
        assert n.reason == "not responding"

    def test_skips_malformed_lines(self):
        output = "not enough pipes\n"
        assert parse_nodes(output) == []

    def test_skips_blank_lines(self):
        output = "\n\ngpu01|gpu|idle|0/32/0/32|256000|256000|gpu:l40s:4|\n\n"
        assert len(parse_nodes(output)) == 1

    def test_reason_null_normalized(self):
        output = "cpu01|cpu|idle|0/64/0/64|512000|512000|(null)|(null)"
        n = parse_nodes(output)[0]
        assert n.reason == ""

    def test_dedupes_node_appearing_in_multiple_partitions(self):
        """sinfo -N emits one line per (node, partition); the parser must
        merge those so the dashboard DataTable doesn't see duplicate keys."""
        output = (
            "gpu01|gpu|idle|0/32/0/32|256000|256000|gpu:l40s:4|\n"
            "gpu01|long|idle|0/32/0/32|256000|256000|gpu:l40s:4|\n"
            "gpu01|debug|idle|0/32/0/32|256000|256000|gpu:l40s:4|\n"
        )
        nodes = parse_nodes(output)
        assert len(nodes) == 1
        assert nodes[0].name == "gpu01"
        assert nodes[0].partition == "gpu,long,debug"

    def test_dedupe_preserves_reason_from_any_row(self):
        output = (
            "cpu01|cpu|drained|0/0/0/64|0|512000|(null)|\n"
            "cpu01|long|drained|0/0/0/64|0|512000|(null)|maintenance\n"
        )
        nodes = parse_nodes(output)
        assert len(nodes) == 1
        assert nodes[0].reason == "maintenance"


class TestParsePartitions:
    def test_aggregates_node_states(self):
        partition_output = "gpu|3|32/64/0/96|gpu:l40s:12|256000|up"
        node_output = (
            "gpu01|gpu|idle|0/32/0/32|256000|256000|gpu:l40s:4|\n"
            "gpu02|gpu|mixed|16/16/0/32|128000|256000|gpu:l40s:4|\n"
            "gpu03|gpu|allocated|32/0/0/32|10000|256000|gpu:l40s:4|\n"
        )
        nodes = parse_nodes(node_output)
        partitions = parse_partitions(partition_output, nodes)
        assert len(partitions) == 1
        p = partitions[0]
        assert p.name == "gpu"
        assert p.nodes_idle == 1
        assert p.nodes_mixed == 1
        assert p.nodes_alloc == 1
        assert p.nodes_down == 0
        assert p.cpus_total == 96
        assert p.gpus_total == 12
        # mixed (4) + alloc (4) = 8 used
        assert p.gpus_used == 8

    def test_partition_marks_down(self):
        partition_output = "cpu|2|0/0/0/128|(null)|512000|down"
        node_output = (
            "cpu01|cpu|drained|0/0/0/64|0|256000|(null)|maint\n"
            "cpu02|cpu|down|0/0/0/64|0|256000|(null)|hw failure\n"
        )
        nodes = parse_nodes(node_output)
        partitions = parse_partitions(partition_output, nodes)
        p = partitions[0]
        assert p.available is False
        assert p.nodes_down == 2

    def test_dedupes_partition_grouped_by_state(self):
        """sinfo groups by state within a partition, so the parser must
        sum the duplicate lines instead of crashing on DuplicateKey."""
        partition_output = (
            "gpu|2|0/64/0/64|gpu:l40s:8|256000|up\n"   # 2 idle nodes
            "gpu|1|32/0/0/32|gpu:l40s:4|256000|up\n"   # 1 allocated node
        )
        node_output = (
            "gpu01|gpu|idle|0/32/0/32|256000|256000|gpu:l40s:4|\n"
            "gpu02|gpu|idle|0/32/0/32|256000|256000|gpu:l40s:4|\n"
            "gpu03|gpu|allocated|32/0/0/32|10000|256000|gpu:l40s:4|\n"
        )
        nodes = parse_nodes(node_output)
        partitions = parse_partitions(partition_output, nodes)
        # Only one partition entry, summed correctly
        assert len(partitions) == 1
        p = partitions[0]
        assert p.nodes_total == 3
        assert p.cpus_total == 96
        assert p.gpus_total == 12
        # Memory shouldn't double — every line repeats the per-node value
        assert p.mem_total_mb == 256000

    def test_multi_partition_node(self):
        """A node belonging to two partitions should bump both partition counts."""
        partition_output = (
            "gpu|1|0/32/0/32|gpu:l40s:4|256000|up\n"
            "long|1|0/32/0/32|gpu:l40s:4|256000|up\n"
        )
        node_output = (
            "gpu01|gpu,long|idle|0/32/0/32|256000|256000|gpu:l40s:4|\n"
        )
        nodes = parse_nodes(node_output)
        partitions = parse_partitions(partition_output, nodes)
        by_name = {p.name: p for p in partitions}
        assert by_name["gpu"].nodes_idle == 1
        assert by_name["long"].nodes_idle == 1


class TestAggregateCapacity:
    def test_basic(self):
        nodes = [
            NodeStats(name="a", state="idle", cpus_alloc=0, cpus_total=32,
                      mem_free_mb=256000, mem_total_mb=256000,
                      gpus_total=4, gpus_used=0),
            NodeStats(name="b", state="allocated", cpus_alloc=32, cpus_total=32,
                      mem_free_mb=10000, mem_total_mb=256000,
                      gpus_total=4, gpus_used=4),
            NodeStats(name="c", state="down", cpus_alloc=0, cpus_total=32,
                      mem_free_mb=0, mem_total_mb=256000),
        ]
        cap = aggregate_capacity(nodes)
        assert cap.nodes_up == 2
        assert cap.nodes_down == 1
        assert cap.cpus_used == 32
        assert cap.cpus_total == 96
        assert cap.gpus_used == 4
        assert cap.gpus_total == 8
        # mem_used = (256000 - 256000) + (256000 - 10000) = 246000 (node c
        # is down, has 0 free + 256000 total so used = 256000; but the
        # aggregation considers mem_total_mb regardless of state).
        assert cap.mem_used_mb == (0 + 246000 + 256000)
        assert cap.mem_total_mb == 768000

    def test_percentages(self):
        cap = ClusterCapacity(
            cpus_used=50, cpus_total=100,
            gpus_used=3, gpus_total=12,
            mem_used_mb=400, mem_total_mb=1600,
        )
        assert cap.cpu_percentage == 50.0
        assert cap.gpu_percentage == 25.0
        assert cap.mem_percentage == 25.0

    def test_zero_totals(self):
        cap = ClusterCapacity()
        assert cap.cpu_percentage == 0.0
        assert cap.gpu_percentage == 0.0
        assert cap.mem_percentage == 0.0

    def test_drain_counted_as_up(self):
        nodes = [
            NodeStats(name="a", state="drained", cpus_total=32),
            NodeStats(name="b", state="idle", cpus_total=32),
        ]
        cap = aggregate_capacity(nodes)
        # Drained nodes are reachable; count them as up but flag the drain.
        assert cap.nodes_up == 2
        assert cap.nodes_drain == 1


class TestFetchSinfo:
    def test_runs_both_commands_and_stitches(self):
        client = MagicMock()
        node_output = (
            "gpu01|gpu|idle|0/32/0/32|256000|256000|gpu:l40s:4|\n"
            "gpu02|gpu|allocated|32/0/0/32|10000|256000|gpu:l40s:4|\n"
        )
        partition_output = "gpu|2|32/32/0/64|gpu:l40s:8|512000|up"

        def fake_execute(cmd, timeout):
            if "-N" in cmd:
                return node_output
            return partition_output

        client.execute.side_effect = fake_execute

        cap, parts, nodes = fetch_sinfo(client)
        assert isinstance(cap, ClusterCapacity)
        assert len(parts) == 1
        assert len(nodes) == 2
        assert parts[0].nodes_idle == 1
        assert parts[0].nodes_alloc == 1
        # 4 used on the allocated node, 0 on idle.
        assert cap.gpus_used == 4
        assert cap.fetched_at  # populated with HH:MM:SS

    def test_format_strings_are_what_we_advertise(self):
        # Guard against accidental edits to the format constants.
        assert SINFO_PARTITION_FMT == "%R|%D|%C|%G|%m|%a"
        assert SINFO_NODE_FMT == "%N|%R|%T|%C|%e|%m|%G|%E"
