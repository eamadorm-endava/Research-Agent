import time
import requests
from typing import Annotated, Optional
from abc import ABC, abstractmethod

from loguru import logger
from google.cloud import firestore
from pydantic import BaseModel, Field

from ..config import (
    GCP_CONFIG,
    GOOGLE_AUTH_CONFIG,
    MICROSOFT_AUTH_CONFIG,
    ATLASSIAN_AUTH_CONFIG,
    FIRESTORE_CONFIG,
)


class TokenData(BaseModel):
    access_token: Annotated[str, Field(description="The current access token")]
    refresh_token: Annotated[
        Optional[str],
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
    def refresh_token(self, refresh_token: str) -> Optional[TokenData]:
        """
        Exchanges a refresh token for a new access token.

        Args:
            refresh_token: str -> The refresh token to use.

        Returns:
            Optional[TokenData] -> The newly acquired token data, or None if failed.
        """
        pass


class GoogleRefreshStrategy(BaseOAuthRefreshStrategy):
    def refresh_token(self, refresh_token: str) -> Optional[TokenData]:
        logger.info("Attempting to refresh Google OAuth token")
        payload = {
            "client_id": GOOGLE_AUTH_CONFIG.CLIENT_ID,
            "client_secret": GOOGLE_AUTH_CONFIG.CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            response = requests.post(GOOGLE_AUTH_CONFIG.TOKEN_URI, data=payload, timeout=20)
            response.raise_for_status()
            data = response.json()

            return TokenData(
                access_token=data["access_token"],
                refresh_token=data.get(
                    "refresh_token", refresh_token
                ),  # Sometimes Google doesn't return a new refresh token
                expires_at=time.time() + float(data["expires_in"]),
            )
        except Exception as e:
            logger.error(f"Failed to refresh Google token: {e}")
            return None


class MicrosoftRefreshStrategy(BaseOAuthRefreshStrategy):
    def refresh_token(self, refresh_token: str) -> Optional[TokenData]:
        logger.info("Attempting to refresh Microsoft OAuth token")
        payload = {
            "client_id": MICROSOFT_AUTH_CONFIG.CLIENT_ID,
            "client_secret": MICROSOFT_AUTH_CONFIG.CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            response = requests.post(MICROSOFT_AUTH_CONFIG.TOKEN_URI, data=payload, timeout=20)
            response.raise_for_status()
            data = response.json()

            return TokenData(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", refresh_token),
                expires_at=time.time() + float(data["expires_in"]),
            )
        except Exception as e:
            logger.error(f"Failed to refresh Microsoft token: {e}")
            return None


class AtlassianRefreshStrategy(BaseOAuthRefreshStrategy):
    def refresh_token(self, refresh_token: str) -> Optional[TokenData]:
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
        except Exception as e:
            logger.error(f"Failed to refresh Atlassian token: {e}")
            return None


class TokenStore:
    """
    Handles secure storage and retrieval of OAuth tokens using Google Cloud Firestore.
    """

    def __init__(self, project_id: Optional[str] = None) -> None:
        """
        Initializes the Firestore client and the refresh strategies.

        Args:
            project_id: Optional[str] -> Target GCP project ID. Defaults to GCP_CONFIG.
        """
        resolved_project_id = project_id or GCP_CONFIG.PROJECT_ID
        self.db = firestore.Client(
            project=resolved_project_id, database=FIRESTORE_CONFIG.DB_NAME
        )
        self.collection_name = FIRESTORE_CONFIG.COLLECTION_NAME

        self.refresh_strategies: dict[str, BaseOAuthRefreshStrategy] = {
            "google": GoogleRefreshStrategy(),
            "microsoft": MicrosoftRefreshStrategy(),
            "atlassian": AtlassianRefreshStrategy(),
        }

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

    def get_token_data(self, user_id: str, provider: str) -> Optional[TokenData]:
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

    def get_valid_access_token(self, user_id: str, provider: str) -> Optional[str]:
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
    ) -> Optional[str]:
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

        strategy = self.refresh_strategies.get(provider)
        if not strategy:
            logger.error(f"No refresh strategy found for provider: {provider}")
            return None

        new_token_data = strategy.refresh_token(token_data.refresh_token)

        if new_token_data:
            self.save_tokens(user_id, provider, new_token_data)
            return new_token_data.access_token

        return None


# Singleton instance for the application to share
token_store = TokenStore()
