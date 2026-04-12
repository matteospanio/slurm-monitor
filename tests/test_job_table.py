"""Tests for the JobTable widget helpers."""

from slurm_monitor.widgets.job_table import _truncate_path


class TestTruncatePath:
    def test_long_path(self):
        assert _truncate_path("/home/user/projects/ml/train") == "../ml/train"

    def test_three_components(self):
        # /home/user has parts ('/', 'home', 'user') = 3 parts, truncated to last 2
        assert _truncate_path("/home/user") == "../home/user"

    def test_single_component(self):
        assert _truncate_path("/home") == "/home"

    def test_empty_string(self):
        assert _truncate_path("") == ""

    def test_custom_components(self):
        assert _truncate_path("/a/b/c/d/e", components=3) == "../c/d/e"

    def test_keeps_last_two_dirs(self):
        assert _truncate_path("/home/spanio/jobs/tmp/mxlGPT") == "../tmp/mxlGPT"
