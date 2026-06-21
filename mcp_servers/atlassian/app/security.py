from .config import ATLASSIAN_API_CONFIG
from .atlassian.client import AtlassianClient


def create_atlassian_client() -> AtlassianClient:
    """Factory to create an AtlassianClient using configured Secret Manager credentials.

    Returns:
        AtlassianClient -> An initialized Atlassian API client.
    """
    creds = ATLASSIAN_API_CONFIG.credentials
    return AtlassianClient(
        email=creds.jira_user_email,
        token=creds.jira_api_token.get_secret_value(),
        instance_url=creds.jira_instance_url,
        cloud_id=creds.jira_cloud_id,
    )
