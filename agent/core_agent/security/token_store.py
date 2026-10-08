import hashlib
import threading
import time
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Annotated

import requests
from google.cloud import firestore
from loguru import logger
from pydantic import BaseModel, Field

from ..config import (
    ATLASSIAN_AUTH_CONFIG,
    FIRESTORE_CONFIG,
    GCP_CONFIG,
    GOOGLE_AUTH_CONFIG,
    MICROSOFT_AUTH_CONFIG,
)


class TokenData(BaseModel):
    access_token: Annotated[str, Field(description="The current access token")]
    refresh_token: Annotated[
        str | None,
        Field(
            description="The refresh token to obtain a new access token", default=None
        ),
    ]
    expires_at: Annotated[
        float, Field(description="Unix timestamp (UTC) when the token expires")
    ]


class BaseOAuthRefreshStrategy(ABC):
    """
    Abstract base class defining the contract for refreshing OAuth tokens
    for different identity providers.
    """

    @abstractmethod
    def refresh_token(self, refresh_token: str) -> TokenData | None:
        """
        Exchanges a refresh token for a new access token.

        Args:
            refresh_token: str -> The refresh token to use.

        Returns:
            Optional[TokenData] -> The newly acquired token data, or None if failed.
        """


class GoogleRefreshStrategy(BaseOAuthRefreshStrategy):
    def refresh_token(self, refresh_token: str) -> TokenData | None:
        logger.info("Attempting to refresh Google OAuth token")
        payload = {
            "client_id": GOOGLE_AUTH_CONFIG.CLIENT_ID,
            "client_secret": GOOGLE_AUTH_CONFIG.CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            response = requests.post(
                GOOGLE_AUTH_CONFIG.TOKEN_URI, data=payload, timeout=20
            )
            response.raise_for_status()
            data = response.json()

            return TokenData(
                access_token=data["access_token"],
                refresh_token=data.get(
                    "refresh_token", refresh_token
                ),  # Sometimes Google doesn't return a new refresh token
                expires_at=time.time() + float(data["expires_in"]),
            )
        except (requests.RequestException, KeyError, ValueError):
            logger.warning("Google token refresh failed")
            return None


class MicrosoftRefreshStrategy(BaseOAuthRefreshStrategy):
    def refresh_token(self, refresh_token: str) -> TokenData | None:
        logger.info("Attempting to refresh Microsoft OAuth token")
        payload = {
            "client_id": MICROSOFT_AUTH_CONFIG.CLIENT_ID,
            "client_secret": MICROSOFT_AUTH_CONFIG.CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            response = requests.post(
                MICROSOFT_AUTH_CONFIG.TOKEN_URI, data=payload, timeout=20
            )
            response.raise_for_status()
            data = response.json()

            return TokenData(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", refresh_token),
                expires_at=time.time() + float(data["expires_in"]),
            )
        except (requests.RequestException, KeyError, ValueError):
            logger.warning("Microsoft token refresh failed")
            return None


class AtlassianRefreshStrategy(BaseOAuthRefreshStrategy):
    def refresh_token(self, refresh_token: str) -> TokenData | None:
        logger.info("Attempting to refresh Atlassian OAuth token")
        payload = {
            "client_id": ATLASSIAN_AUTH_CONFIG.CLIENT_ID,
            "client_secret": ATLASSIAN_AUTH_CONFIG.CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            response = requests.post(
                ATLASSIAN_AUTH_CONFIG.TOKEN_URI, json=payload, timeout=20
            )  # Atlassian uses JSON
            response.raise_for_status()
            data = response.json()

            return TokenData(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", refresh_token),
                expires_at=time.time() + float(data["expires_in"]),
            )
        except (requests.RequestException, KeyError, ValueError):
            logger.warning("Atlassian token refresh failed")
            return None


class TokenStore:
    """
    Handles secure storage and retrieval of OAuth tokens using Google Cloud Firestore.
    """

    def __init__(self, project_id: str | None = None) -> None:
        """
        Initializes the Firestore client and the refresh strategies.

        Args:
            project_id: Optional[str] -> Target GCP project ID. Defaults to GCP_CONFIG.
        """
        resolved_project_id = project_id or GCP_CONFIG.PROJECT_ID
        self.project_id = resolved_project_id
        self._db = None
        self._client_lock = threading.Lock()
        self.collection_name = FIRESTORE_CONFIG.COLLECTION_NAME

        self.refresh_strategies: dict[str, BaseOAuthRefreshStrategy] = {
            "google": GoogleRefreshStrategy(),
            "microsoft": MicrosoftRefreshStrategy(),
            "atlassian": AtlassianRefreshStrategy(),
        }

    @property
    def db(self):
        """Create ADC-backed clients on first use, not on module import."""
        with self._client_lock:
            if self._db is None:
                self._db = firestore.Client(
                    project=self.project_id, database=FIRESTORE_CONFIG.DB_NAME
                )
            return self._db

    def save_tokens(self, user_id: str, provider: str, token_data: TokenData) -> None:
        """
        Saves or updates OAuth tokens for a specific user and provider.

        Args:
            user_id: str -> The user's unique identifier (e.g., email).
            provider: str -> The identity provider (e.g., 'google', 'microsoft', 'atlassian').
            token_data: TokenData -> The token payload.

        Returns:
            None -> Saves the data directly to Firestore.
        """
        logger.info(f"Saving {provider} tokens for user: {user_id}")

        doc_ref = self.db.collection(self.collection_name).document(user_id)

        # We merge so we don't overwrite other providers the user might have saved
        doc_ref.set({provider: token_data.model_dump()}, merge=True)

        logger.debug(f"Tokens saved successfully for {user_id} - {provider}")

    def get_token_data(self, user_id: str, provider: str) -> TokenData | None:
        """
        Retrieves the token data for a specific user and provider.

        Args:
            user_id: str -> The user's unique identifier (e.g., email).
            provider: str -> The identity provider.

        Returns:
            Optional[TokenData] -> The token data if it exists, otherwise None.
        """
        logger.debug(f"Retrieving {provider} tokens for user: {user_id}")

        doc_ref = self.db.collection(self.collection_name).document(user_id)
        doc = doc_ref.get()

        if not doc.exists:
            logger.debug(f"No token document found for user: {user_id}")
            return None

        data = doc.to_dict()
        provider_data = data.get(provider)

        if not provider_data:
            logger.debug(
                f"No tokens found for provider '{provider}' under user {user_id}"
            )
            return None

        return TokenData(**provider_data)

    def get_valid_access_token(self, user_id: str, provider: str) -> str | None:
        """
        Retrieves a valid access token. If the token is expired, it uses the specific
        provider strategy to refresh it.

        Args:
            user_id: str -> The user's unique identifier (e.g., email).
            provider: str -> The identity provider.

        Returns:
            Optional[str] -> A valid access token string, or None if unavailable/refresh fails.
        """
        token_data = self.get_token_data(user_id, provider)

        if not token_data:
            return None

        # Check if expired (with a 60 seconds buffer). time.time() is UTC.
        if time.time() >= (token_data.expires_at - 60):
            logger.info(
                f"Access token for {user_id} ({provider}) is expired. Refreshing..."
            )
            return self._refresh_access_token(user_id, provider, token_data)

        return token_data.access_token

    def _refresh_access_token(
        self, user_id: str, provider: str, token_data: TokenData
    ) -> str | None:
        """
        Internal method to refresh an expired access token using the provider's API.

        Args:
            user_id: str -> The user's unique identifier.
            provider: str -> The identity provider.
            token_data: TokenData -> The existing token data containing the refresh token.

        Returns:
            Optional[str] -> The new access token, or None if refresh fails.
        """
        if not token_data.refresh_token:
            logger.warning(f"No refresh token available for {user_id} ({provider})")
            return None

        return self._refresh_with_lease(user_id, provider)

    def _refresh_with_lease(self, user_id: str, provider: str) -> str | None:
        """Coordinate refresh across instances so rotating credentials are not reused."""
        lock_id = hashlib.sha256(f"{user_id}:{provider}".encode()).hexdigest()
        reference = self.db.collection(
            f"{self.collection_name}_refresh_locks"
        ).document(lock_id)
        owner = uuid.uuid4().hex
        deadline = time.monotonic() + 25
        while not self._acquire_lease(reference, owner):
            current = self.get_token_data(user_id, provider)
            if current and current.expires_at > time.time() + 60:
                return current.access_token
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.5)
        try:
            current = self.get_token_data(user_id, provider)
            if not current:
                return None
            if current.expires_at > time.time() + 60:
                return current.access_token
            return self._perform_refresh(user_id, provider, current)
        finally:
            self._release_lease(reference, owner)

    def _acquire_lease(self, reference, owner: str) -> bool:
        """Acquire a short lease with a Firestore transaction."""

        @firestore.transactional
        def acquire(transaction):
            snapshot = reference.get(transaction=transaction)
            existing = snapshot.to_dict() if snapshot.exists else {}
            if existing.get(
                "expires_at", datetime.min.replace(tzinfo=UTC)
            ) > datetime.now(UTC):
                return False
            transaction.set(
                reference,
                {
                    "owner": owner,
                    "expires_at": datetime.now(UTC) + timedelta(seconds=90),
                },
            )
            return True

        return acquire(self.db.transaction())

    def _release_lease(self, reference, owner: str) -> None:
        """Only the current owner can release a lease."""

        @firestore.transactional
        def release(transaction):
            snapshot = reference.get(transaction=transaction)
            if snapshot.exists and snapshot.to_dict().get("owner") == owner:
                transaction.delete(reference)

        release(self.db.transaction())

    def _perform_refresh(
        self, user_id: str, provider: str, token_data: TokenData
    ) -> str | None:
        """Refresh once while holding the distributed lease."""
        strategy = self.refresh_strategies.get(provider)
        if not strategy:
            logger.error(f"No refresh strategy found for provider: {provider}")
            return None

        new_token_data = strategy.refresh_token(token_data.refresh_token)

        if new_token_data:
            return self._save_rotated_tokens(
                user_id, provider, token_data, new_token_data
            )

        return None

    def _save_rotated_tokens(
        self, user_id: str, provider: str, previous: TokenData, refreshed: TokenData
    ) -> str | None:
        """Never overwrite credentials from a reconnect that completed during refresh."""
        reference = self.db.collection(self.collection_name).document(user_id)

        @firestore.transactional
        def persist(transaction):
            snapshot = reference.get(transaction=transaction)
            record = snapshot.to_dict() if snapshot.exists else {}
            current = record.get(provider)
            if not current:
                return None
            if (
                current.get("access_token") != previous.access_token
                or current.get("refresh_token") != previous.refresh_token
            ):
                return (
                    current["access_token"]
                    if current["expires_at"] > time.time() + 60
                    else None
                )
            transaction.set(reference, {provider: refreshed.model_dump()}, merge=True)
            return refreshed.access_token

        return persist(self.db.transaction())


# Singleton instance for the application to share
token_store = TokenStore()
