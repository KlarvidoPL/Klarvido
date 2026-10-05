"""
Outbound requests to identity providers.

Connection settings and identity provider discovery documents are data that a tenant admin or the IdP controls.
Before the server calls such a URL it must be public: https, a public address, and no redirects. Without this an
admin could point a connection at cloud metadata or at internal services.
"""

import ipaddress
import socket
from urllib.parse import urlparse

import requests
from django.conf import settings

LOCAL_HOSTS = {"localhost", "127.0.0.1"}
REQUEST_TIMEOUT_SECONDS = 10


class UnsafeOutboundURL(ValueError):
    """The URL is not one the server may call for an identity provider."""


def _is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified
    )


def validate_public_url(url: str) -> str:
    """Return the URL if the server may call it, otherwise raise UnsafeOutboundURL.

    Plain http is accepted only for localhost while DEBUG is on, so a local Keycloak keeps working.
    """
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    if not host:
        raise UnsafeOutboundURL("Identity provider URL has no host")

    local_allowed = settings.DEBUG and host in LOCAL_HOSTS
    if local_allowed and parsed.scheme in ("http", "https"):
        return url
    if parsed.scheme != "https":
        raise UnsafeOutboundURL("Identity provider URL must use https")

    try:
        addresses = socket.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise UnsafeOutboundURL("Identity provider host cannot be resolved")

    for info in addresses:
        if not _is_public_address(info[4][0]):
            raise UnsafeOutboundURL("Identity provider URL points at a private or internal address")
    return url


def safe_request(method: str, url: str, timeout: int = REQUEST_TIMEOUT_SECONDS, **kwargs) -> requests.Response:
    """Call an identity provider URL after validating it. Redirects are not followed, so a public URL cannot
    bounce the request to an internal address. A redirect comes back as its own response for the caller to see."""
    validate_public_url(url)
    return requests.request(method, url, allow_redirects=False, timeout=timeout, **kwargs)
