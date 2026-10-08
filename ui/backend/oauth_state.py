"""Bind an OAuth exchange to the authenticated user, browser and provider."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from google.cloud import firestore

from agent.core_agent.security.token_store import token_store

from .config import UI_CONFIG


def digest(value: str) -> str:
    """Hash high-entropy state values before using them as document identifiers."""
    return hashlib.sha256(value.encode()).hexdigest()


def create_state(user: str, provider: str, browser_session_id: str) -> dict[str, str]:
    """Persist a short-lived authorization transaction and PKCE verifier."""
    state, verifier = (secrets.token_urlsafe(32) for _ in range(2))
    token_store.db.collection(f"{token_store.collection_name}_oauth_states").document(
        digest(state)
    ).set(
        {
            "user": user,
            "provider": provider,
            "browser_session_id": browser_session_id,
            "verifier": verifier,
            "expires_at": datetime.now(UTC)
            + timedelta(seconds=UI_CONFIG.OAUTH_STATE_SECONDS),
        }
    )
    return {"state": state, "verifier": verifier}


def consume_state(
    state: str, browser_session_id: str, user: str, provider: str
) -> dict[str, str]:
    """Atomically consume state; reject expired, replayed or mismatched callbacks."""
    if not state or len(state) > 128 or not browser_session_id:
        raise HTTPException(400, "Invalid OAuth transaction")
    reference = token_store.db.collection(
        f"{token_store.collection_name}_oauth_states"
    ).document(digest(state))

    @firestore.transactional
    def consume(transaction):
        snapshot = reference.get(transaction=transaction)
        record = snapshot.to_dict() if snapshot.exists else None
        if (
            not record
            or record["expires_at"] <= datetime.now(UTC)
            or record["user"] != user
            or record["provider"] != provider
            or not secrets.compare_digest(
                record.get("browser_session_id", ""), browser_session_id
            )
        ):
            raise HTTPException(400, "Invalid OAuth transaction")
        transaction.delete(reference)
        return {
            "verifier": record["verifier"],
        }

    return consume(token_store.db.transaction())
