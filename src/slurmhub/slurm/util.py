"""Shared parsing helpers for the Slurm command layer."""


def time_to_seconds(time_str: str) -> int:
    """Convert a Slurm time string to total seconds for comparison.

    Supports formats: MM:SS, HH:MM:SS, D-HH:MM:SS

    Args:
        time_str: Time string from Slurm output

    Returns:
        Total seconds, or 0 if parsing fails
    """
    try:
        days = 0
        if "-" in time_str:
            day_part, time_str = time_str.split("-", 1)
            days = int(day_part)

        parts = time_str.split(":")
        if len(parts) == 3:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        elif len(parts) == 2:
            hours = 0
            minutes, seconds = int(parts[0]), int(parts[1])
        else:
            return 0

        return days * 86400 + hours * 3600 + minutes * 60 + seconds
    except (ValueError, IndexError):
        return 0
