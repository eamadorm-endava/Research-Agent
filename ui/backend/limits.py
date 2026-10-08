"""Shared SlowAPI policy required by the repository's security rules."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import UI_CONFIG

limiter = Limiter(key_func=get_remote_address)


def request_limit() -> str:
    """Read the configured per-instance request limit."""
    return f"{UI_CONFIG.REQUESTS_PER_MINUTE}/minute"
