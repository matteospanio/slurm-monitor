"""OSC 52 clipboard helpers.

OSC 52 is a terminal escape sequence that asks the terminal emulator to
put a value into the system clipboard. It works through SSH because the
escape sequence is delivered to the *local* terminal, which is the one
that has the clipboard. Supported by iTerm2, WezTerm, kitty, Alacritty,
and tmux (with ``set-clipboard on``).

If clipboard writing fails (no TTY, terminal does not honor the
escape), the function returns ``False`` and the caller can decide
whether to surface a warning.
"""

import base64
import os
import sys


def build_osc52_sequence(text: str) -> bytes:
    """Encode ``text`` as an OSC 52 ``c`` (clipboard) escape sequence."""
    payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"\x1b]52;c;{payload}\x07".encode("ascii")


def copy_osc52(text: str, fileobj=None) -> bool:
    """Write the OSC 52 escape so the terminal copies ``text``.

    Args:
        text: arbitrary string. May contain newlines (the terminal will
            paste them verbatim).
        fileobj: optional binary-mode file. Defaults to ``sys.stdout``'s
            buffer or ``/dev/tty`` if stdout is not a TTY. Test-friendly.

    Returns:
        ``True`` on success, ``False`` if nothing was written (e.g. no
        TTY available).
    """
    if not text:
        return False

    sequence = build_osc52_sequence(text)

    if fileobj is not None:
        try:
            fileobj.write(sequence)
            try:
                fileobj.flush()
            except Exception:
                pass
            return True
        except Exception:
            return False

    # Prefer the real terminal device when stdout is captured (e.g. by
    # Textual's screen buffer). This is what makes copy work even
    # though the TUI owns stdout.
    for path_or_attr in ("/dev/tty",):
        try:
            with open(path_or_attr, "wb", buffering=0) as tty:
                tty.write(sequence)
            return True
        except Exception:
            pass

    # Fallback: try stdout's underlying buffer
    try:
        buf = getattr(sys.stdout, "buffer", None)
        if buf is None:
            return False
        if not os.isatty(buf.fileno()):
            return False
        buf.write(sequence)
        buf.flush()
        return True
    except Exception:
        return False
