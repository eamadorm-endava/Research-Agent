"""Use agent event timestamps rather than delivery latency for tool durations."""

import math


def event_timestamp(value: float | str | None) -> float | None:
    """Read a finite event timestamp; omit missing or malformed metadata."""
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    return timestamp if math.isfinite(timestamp) and timestamp >= 0 else None


def duration_suffix(start: float | None, end: float | None) -> str:
    """Label a measured event interval without implying unmeasured zero durations."""
    if start is None or end is None or end <= start:
        return ""
    duration = end - start
    return " - <0.1s" if duration < 0.1 else f" - {duration:.1f}s"
