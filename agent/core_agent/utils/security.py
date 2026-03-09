import google.auth
from google.auth.transport.requests import Request
import google.oauth2.id_token
import logging


def get_id_token(audience: str) -> str:
    """
    Generate a valid IDToken to call a GCP service (CloudRun).

    It first tries to retrieve an ID token from the server that is executing
    the code, and then it tries to retrieve a personal token (when running locally).

    The 'audience' must be the base URL of the Cloud Run service.

    Args:
        audience: str -> The CloudRun base URL that wants to call

    Returns:
        token: str -> The ID token
    """
    try:
        logging.debug("Retrieving ID token from server...")
        request = Request()
        id_token = google.oauth2.id_token.fetch_id_token(request, audience)
        logging.debug("IDToken successfully retrieved from server...")
    except Exception as e:
        logging.debug(f"Attempt to retrieve IDtoken from server failed: {e}")
        logging.debug("Retrieving token from personal credentials... (local dev only)")
        credentials, _ = google.auth.default()
        credentials.refresh(request)
        id_token = getattr(credentials, "id_token", None)
        if id_token:
            logging.debug("Token from personal credentials successfully retrieved")
        else:
            logging.warning("No ID token generated, neither personal nor server")

    return id_token
