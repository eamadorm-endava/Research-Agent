from datetime import datetime


def calculate_duration(initial_time: datetime, final_time: datetime) -> str:
    """Calculates the duration between two datetime objects in 'Xh Ym Zs' format.

    Args:
        initial_time (datetime): The starting time.
        final_time (datetime): The ending time.

    Returns:
        str: Formatted duration string (e.g., '1h 25m 30s').
    """
    if not (initial_time and final_time):
        return "0h 0m 0s"

    delta = final_time - initial_time
    total_seconds = abs(int(delta.total_seconds()))

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    return f"{hours}h {minutes}m {seconds}s"
