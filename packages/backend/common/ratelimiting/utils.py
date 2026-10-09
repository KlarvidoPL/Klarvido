"""
Rate Limiting Utilities.

Helper functions for rate limiting operations.
"""

import ipaddress
import logging
from typing import Optional, Union

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest

from .constants import RateLimitKey


logger = logging.getLogger(__name__)

# Unresolvable/unparseable peers must still land in a single stable rate-limit bucket rather
# than bypassing the limit entirely - see rate_limit_ip() below.
UNKNOWN_IP_BUCKET = "unknown"


def _trusted_proxy_networks():
    # TRUSTED_PROXIES is the canonical setting; AUTH_AUDIT_TRUSTED_PROXIES (the older,
    # audit-only name) is read as a fallback live at call time, not aliased once at settings
    # load - so a deployment (or a test) only has to set the one it means, and overriding
    # either one via Django's `settings` object at runtime is honored immediately.
    raw = getattr(settings, "TRUSTED_PROXIES", None) or getattr(settings, "AUTH_AUDIT_TRUSTED_PROXIES", None) or []
    networks = []
    for value in raw:
        try:
            networks.append(ipaddress.ip_network(value))
        except ValueError:
            logger.warning("Ignoring invalid trusted-proxy entry: %s", value)
    return networks


def get_client_ip(request: HttpRequest) -> Optional[str]:
    """
    The single trusted-proxy-aware client IP resolver used across the codebase (rate limiting,
    passkey throttling, authentication audit logging). X-Forwarded-For is only trusted through
    hops that match a network in settings.TRUSTED_PROXIES - an attacker-controlled browser can
    set that header to anything, so without a configured trust chain it is ignored entirely and
    the direct peer (REMOTE_ADDR) is used. Walks the forwarded chain right-to-left (closest hop
    first), continuing past each hop that is itself a trusted proxy and stopping at the first
    hop that isn't (or the start of the chain).

    Args:
        request: Django HttpRequest object (or an object with a `._request` attribute wrapping
            one, e.g. GraphQL's info.context)

    Returns:
        Client IP address string, or None if REMOTE_ADDR itself cannot be parsed.
    """
    if request is None:
        return None
    request = getattr(request, "_request", request)
    try:
        peer = ipaddress.ip_address(request.META.get("REMOTE_ADDR", ""))
    except ValueError:
        return None

    networks = _trusted_proxy_networks()
    if networks and any(peer in network for network in networks):
        chain = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
        for raw in reversed(chain):
            raw = raw.strip()
            if not raw:
                continue
            try:
                candidate = ipaddress.ip_address(raw)
            except ValueError:
                break
            peer = candidate
            if not any(peer in network for network in networks):
                break

    return str(peer)


def rate_limit_ip(request: HttpRequest) -> str:
    """Never-None variant of get_client_ip() for building rate-limit cache keys, where a bare
    None would either collide every unresolvable client into the literal string "None" or (if a
    caller treats None as "skip limiting") bypass the limit outright. Use this, not
    get_client_ip(), whenever the result becomes part of a rate-limit identifier."""
    return get_client_ip(request) or UNKNOWN_IP_BUCKET


def get_user_id(request: HttpRequest) -> Optional[str]:
    """
    Get user ID from request if authenticated.

    Args:
        request: Django HttpRequest object

    Returns:
        User ID string or None if not authenticated
    """
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        return str(user.id)
    return None


def get_tenant_id(request: HttpRequest) -> Optional[str]:
    """
    Get tenant ID from request context.

    Args:
        request: Django HttpRequest object

    Returns:
        Tenant ID string or None if not in tenant context
    """
    # Try direct tenant attribute (set by middleware)
    tenant = getattr(request, "tenant", None)
    if tenant:
        return str(tenant.id)

    # Try from URL kwargs
    if hasattr(request, "resolver_match") and request.resolver_match:
        return request.resolver_match.kwargs.get("tenant_id")

    return None


def get_rate_limit_key(
    request: HttpRequest,
    key_type: Union[RateLimitKey, str],
    group: str = "",
) -> str:
    """
    Generate a cache key for rate limiting.

    Args:
        request: Django HttpRequest object
        key_type: How to identify the entity (IP, user, tenant, etc.)
        group: Optional group name for the rate limit

    Returns:
        Cache key string for rate limit tracking

    Example:
        >>> get_rate_limit_key(request, RateLimitKey.USER, 'auth.login')
        'ratelimit:auth.login:user:42'
    """
    key_type = RateLimitKey(key_type) if isinstance(key_type, str) else key_type

    # Determine the identifier based on key type
    if key_type == RateLimitKey.IP:
        identifier = rate_limit_ip(request)
    elif key_type == RateLimitKey.USER:
        identifier = get_user_id(request)
        if not identifier:
            # Fall back to IP if not authenticated
            identifier = f"anon:{rate_limit_ip(request)}"
    elif key_type == RateLimitKey.USER_OR_IP:
        identifier = get_user_id(request)
        identifier = f"ip:{rate_limit_ip(request)}" if not identifier else f"user:{identifier}"
    elif key_type == RateLimitKey.TENANT:
        identifier = get_tenant_id(request)
        if not identifier:
            identifier = f"no_tenant:{rate_limit_ip(request)}"
    elif key_type == RateLimitKey.USER_TENANT:
        user_id = get_user_id(request) or f"anon:{rate_limit_ip(request)}"
        tenant_id = get_tenant_id(request) or "no_tenant"
        identifier = f"{user_id}:{tenant_id}"
    else:
        identifier = rate_limit_ip(request)

    # Build the cache key
    parts = ["ratelimit"]
    if group:
        parts.append(group)
    parts.append(key_type.value)
    parts.append(identifier)

    return ":".join(parts)


def get_rate_limit_key_ws(
    user_id: Optional[str],
    tenant_id: Optional[str],
    key_type: Union[RateLimitKey, str],
    group: str = "",
    client_ip: str = "127.0.0.1",
) -> str:
    """
    Generate a cache key for WebSocket rate limiting.

    Similar to get_rate_limit_key but for WebSocket contexts
    where we don't have a standard HttpRequest.

    Args:
        user_id: User ID string or None
        tenant_id: Tenant ID string or None
        key_type: How to identify the entity
        group: Optional group name
        client_ip: Client IP address

    Returns:
        Cache key string
    """
    key_type = RateLimitKey(key_type) if isinstance(key_type, str) else key_type

    if key_type == RateLimitKey.IP:
        identifier = client_ip
    elif key_type == RateLimitKey.USER:
        identifier = user_id or f"anon:{client_ip}"
    elif key_type == RateLimitKey.USER_OR_IP:
        identifier = f"user:{user_id}" if user_id else f"ip:{client_ip}"
    elif key_type == RateLimitKey.TENANT:
        identifier = tenant_id or f"no_tenant:{client_ip}"
    elif key_type == RateLimitKey.USER_TENANT:
        u = user_id or f"anon:{client_ip}"
        t = tenant_id or "no_tenant"
        identifier = f"{u}:{t}"
    else:
        identifier = client_ip

    parts = ["ratelimit"]
    if group:
        parts.append(group)
    parts.append(key_type.value)
    parts.append(identifier)

    return ":".join(parts)


def parse_rate_string(rate: str) -> tuple[int, int]:
    """
    Parse a rate limit string into count and window.

    Args:
        rate: Rate string like '10/min', '100/hour', '1000/day'

    Returns:
        Tuple of (count, window_seconds)

    Example:
        >>> parse_rate_string('10/min')
        (10, 60)
        >>> parse_rate_string('100/hour')
        (100, 3600)
    """
    if "/" not in rate:
        raise ValueError(f"Invalid rate format: {rate}")

    count_str, period = rate.split("/")
    count = int(count_str)

    # Parse period
    period = period.lower().strip()
    if period in ("s", "sec", "second"):
        window = 1
    elif period in ("m", "min", "minute"):
        window = 60
    elif period in ("h", "hr", "hour"):
        window = 3600
    elif period in ("d", "day"):
        window = 86400
    else:
        # Try to parse as seconds
        try:
            window = int(period)
        except ValueError:
            raise ValueError(f"Unknown rate period: {period}")

    return count, window


def check_rate_limit(
    key: str,
    rate: str,
    increment: bool = True,
) -> tuple[bool, int, int]:
    """
    Check if a rate limit has been exceeded.

    Args:
        key: Cache key for the rate limit
        rate: Rate string (e.g., '10/min')
        increment: Whether to increment the counter

    Returns:
        Tuple of (is_limited, current_count, remaining)

    Example:
        >>> is_limited, count, remaining = check_rate_limit('ratelimit:auth:ip:1.2.3.4', '10/min')
        >>> if is_limited:
        ...     raise RateLimitExceeded()
    """
    count, window = parse_rate_string(rate)

    # Get current count
    current = cache.get(key, 0)

    if increment:
        # Use cache.incr for atomic increment, with fallback for new keys
        try:
            current = cache.incr(key)
        except ValueError:
            # Key doesn't exist, set it
            cache.set(key, 1, window)
            current = 1

    is_limited = current > count
    remaining = max(0, count - current)

    return is_limited, current, remaining


def get_remaining_requests(key: str, rate: str) -> int:
    """
    Get the number of remaining requests before rate limit is hit.

    Args:
        key: Cache key for the rate limit
        rate: Rate string

    Returns:
        Number of remaining requests
    """
    count, _ = parse_rate_string(rate)
    current = cache.get(key, 0)
    return max(0, count - current)


def reset_rate_limit(key: str):
    """
    Reset a rate limit counter.

    Args:
        key: Cache key for the rate limit
    """
    cache.delete(key)


def get_rate_limit_info(key: str, rate: str) -> dict:
    """
    Get detailed rate limit information.

    Args:
        key: Cache key for the rate limit
        rate: Rate string

    Returns:
        Dict with rate limit information
    """
    count, window = parse_rate_string(rate)
    current = cache.get(key, 0)

    return {
        "limit": count,
        "remaining": max(0, count - current),
        "used": current,
        "window_seconds": window,
        "is_limited": current > count,
    }
