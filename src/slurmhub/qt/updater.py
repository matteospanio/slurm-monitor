"""In-app update check (notify-only).

On startup a worker GETs the GitHub *latest release* and compares its tag to the
running version. If newer, the main window shows a dismissible banner linking to
the download page. No download or self-update happens — that keeps the app free
of code-signing/auto-update machinery (a documented limitation).
"""

import json
import urllib.request
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Optional

REPO = "matteospanio/slurmhub"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
_API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"


@dataclass
class UpdateInfo:
    version: str
    url: str


def current_version() -> str:
    try:
        return version("slurmhub")
    except PackageNotFoundError:  # pragma: no cover — running from a checkout
        return "0.0.0"


def _version_tuple(value: str) -> tuple[int, ...]:
    """Parse a (possibly ``v``-prefixed) dotted version into an int tuple.

    Non-numeric trailers (``1.2.0rc1``) are truncated at the first non-digit so
    comparisons stay total; unparseable parts become 0.
    """
    cleaned = value.strip().lstrip("vV")
    parts: list[int] = []
    for chunk in cleaned.split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def is_newer(latest: str, current: str) -> bool:
    """True if ``latest`` is a strictly newer version than ``current``."""
    return _version_tuple(latest) > _version_tuple(current)


def fetch_latest_release(
    repo: str = REPO, timeout: float = 5.0
) -> Optional[tuple[str, str]]:
    """Return ``(tag_name, html_url)`` for the latest release, or None on error."""
    request = urllib.request.Request(
        _API_LATEST if repo == REPO else f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "slurmhub"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 — offline / rate-limited / no release yet
        return None
    tag = data.get("tag_name")
    url = data.get("html_url") or RELEASES_PAGE
    return (tag, url) if tag else None


def check_for_update(
    current: Optional[str] = None, repo: str = REPO, timeout: float = 5.0
) -> Optional[UpdateInfo]:
    """Return :class:`UpdateInfo` if a newer release exists, else None."""
    current = current or current_version()
    latest = fetch_latest_release(repo, timeout)
    if latest is None:
        return None
    tag, url = latest
    return UpdateInfo(version=tag, url=url) if is_newer(tag, current) else None
