from urllib.parse import urlparse

ATLASSIAN_CLOUD_HOST_SUFFIX = ".atlassian.net"


def is_atlassian_cloud_url(url: str) -> bool:
    """
    Returns True when the URL host is an Atlassian Cloud site.

    The check intentionally parses the URL and validates only the hostname.
    Substring checks against the raw URL are unsafe because an allowed host can
    be embedded in the path, query string, userinfo, or in a look-alike host such
    as evil-atlassian.net.
    """
    if not url:
        return False

    parsed = urlparse(url)
    hostname = parsed.hostname

    # Be tolerant of host-only configuration values while still validating the
    # parsed hostname rather than searching the raw string.
    if hostname is None and "://" not in url:
        hostname = urlparse(f"https://{url}").hostname

    if not hostname:
        return False

    hostname = hostname.rstrip(".").lower()
    return hostname.endswith(ATLASSIAN_CLOUD_HOST_SUFFIX)
