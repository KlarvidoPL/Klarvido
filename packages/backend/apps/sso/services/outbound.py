"""
Outbound requests to identity providers.

Connection settings and identity provider discovery documents are data that a tenant admin or the IdP controls.
Before the server calls such a URL it must be public: https, a public address, and no redirects. Without this an
admin could point a connection at cloud metadata or at internal services.

The address is checked once and the connection is made to that same address. Otherwise a DNS server could answer
with a public address for the check and a private one for the connection (DNS rebinding). The hostname is still
used for TLS, so the certificate must match the name in the URL.
"""

import ipaddress
import socket
from urllib.parse import urlparse

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPSConnection
from urllib3.connectionpool import HTTPSConnectionPool
from urllib3.util.connection import create_connection

# host.docker.internal lets the backend container reach a Keycloak published on the host
LOCAL_HOSTS = {"localhost", "127.0.0.1", "host.docker.internal"}
REQUEST_TIMEOUT_SECONDS = 10


class UnsafeOutboundURL(ValueError):
    """The URL is not one the server may call for an identity provider."""


def _is_public_address(address: str) -> bool:
    try:
        # Drop an IPv6 zone index such as "fe80::1%eth0", which ipaddress does not accept
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified
    )


def _resolve_addresses(host: str, port: int) -> list:
    """Every address the host resolves to. Kept as one function so tests can stub DNS."""
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise UnsafeOutboundURL("Identity provider host cannot be resolved")
    return [info[4][0] for info in infos]


def _public_address(url: str) -> str | None:
    """The address to connect to for this URL. None means the local development exception applies.

    Raises UnsafeOutboundURL when the server may not call the URL at all.
    """
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    if not host:
        raise UnsafeOutboundURL("Identity provider URL has no host")

    # Plain http is accepted only for localhost while DEBUG is on, so a local Keycloak keeps working
    local_allowed = settings.DEBUG and host in LOCAL_HOSTS
    if local_allowed and parsed.scheme in ("http", "https"):
        return None
    if parsed.scheme != "https":
        raise UnsafeOutboundURL("Identity provider URL must use https")

    addresses = _resolve_addresses(host, parsed.port or 443)
    if not addresses or not all(_is_public_address(address) for address in addresses):
        raise UnsafeOutboundURL("Identity provider URL points at a private or internal address")
    return addresses[0]


def validate_public_url(url: str) -> str:
    """Return the URL if the server may call it, otherwise raise UnsafeOutboundURL."""
    _public_address(url)
    return url


class _PinnedHTTPSConnection(HTTPSConnection):
    """Opens the TCP connection to the checked address. TLS still uses the host from the URL for SNI and for
    certificate verification."""

    pinned_address = ""

    def _new_conn(self):
        return create_connection(
            (self.pinned_address or self.host, self.port),
            self.timeout,
            source_address=self.source_address,
            socket_options=self.socket_options,
        )


def _pinned_pool_class(address: str):
    connection_class = type("PinnedHTTPSConnection", (_PinnedHTTPSConnection,), {"pinned_address": address})

    class PinnedHTTPSConnectionPool(HTTPSConnectionPool):
        ConnectionCls = connection_class

    return PinnedHTTPSConnectionPool


class PinnedAddressAdapter(HTTPAdapter):
    """Sends every https request to the given address, whatever the hostname resolves to at connect time."""

    def __init__(self, address: str, **kwargs):
        self.address = address
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {"https": _pinned_pool_class(self.address)}


def safe_request(method: str, url: str, timeout: int = REQUEST_TIMEOUT_SECONDS, **kwargs) -> requests.Response:
    """Call an identity provider URL after validating it. The connection goes to the validated address, and
    redirects are not followed, so a public URL cannot bounce the request to an internal address."""
    address = _public_address(url)
    if address is None:
        return requests.request(method, url, allow_redirects=False, timeout=timeout, **kwargs)

    session = requests.Session()
    try:
        session.mount("https://", PinnedAddressAdapter(address))
        return session.request(method, url, allow_redirects=False, timeout=timeout, **kwargs)
    finally:
        session.close()
