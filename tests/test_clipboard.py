"""Tests for the OSC 52 clipboard helper."""

import base64
import io

from slurmhub.tui.widgets._clipboard import build_osc52_sequence, copy_osc52


class TestBuildOsc52Sequence:
    def test_starts_with_csi_and_terminator(self):
        seq = build_osc52_sequence("hello")
        assert seq.startswith(b"\x1b]52;c;")
        assert seq.endswith(b"\x07")

    def test_payload_is_base64_of_input(self):
        seq = build_osc52_sequence("hello world")
        # Strip the header and BEL
        payload = seq[len(b"\x1b]52;c;") : -1]
        assert base64.b64decode(payload).decode() == "hello world"

    def test_unicode_handled(self):
        seq = build_osc52_sequence("café")
        payload = seq[len(b"\x1b]52;c;") : -1]
        assert base64.b64decode(payload).decode("utf-8") == "café"


class TestCopyOsc52ToFileobj:
    def test_writes_full_sequence_to_supplied_fileobj(self):
        buf = io.BytesIO()
        ok = copy_osc52("abc", fileobj=buf)
        assert ok is True
        assert buf.getvalue() == build_osc52_sequence("abc")

    def test_empty_input_returns_false(self):
        buf = io.BytesIO()
        assert copy_osc52("", fileobj=buf) is False
        assert buf.getvalue() == b""

    def test_failing_fileobj_returns_false(self):
        class Boom:
            def write(self, data):
                raise OSError("nope")

        assert copy_osc52("abc", fileobj=Boom()) is False
