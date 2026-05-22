"""Shared helpers reused across widget modules."""

from pathlib import PurePosixPath


def truncate_path(path: str, components: int = 2) -> str:
    """Truncate a path to the last N components.

    Example: '/home/user/projects/ml/train' -> '../ml/train'
    """
    if not path:
        return ""
    parts = PurePosixPath(path).parts
    if len(parts) <= components:
        return path
    return "../" + "/".join(parts[-components:])
