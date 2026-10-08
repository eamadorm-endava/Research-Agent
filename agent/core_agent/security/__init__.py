"""Expose token storage without importing ADK telemetry into the UI backend."""

from .token_store import token_store

__all__ = ["clear_id_token_cache", "get_ge_oauth_token", "get_id_token", "token_store"]


def __getattr__(name):
    """Load ADK-specific authentication only when an agent requests it."""
    if name in {"clear_id_token_cache", "get_id_token", "get_ge_oauth_token"}:
        from . import auth

        return getattr(auth, name)
    raise AttributeError(name)
