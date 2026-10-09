"""Legacy import path, kept so existing `from common.graphql import ratelimit` call sites and
their `@ratelimit.ratelimit(...)` usage don't need to change. Delegates to
common.ratelimiting.decorators.graphql_ratelimit, which adds centralized rate configuration and
a fail_closed option (see E06 in EMAIL_PASSWORD_SECURITY_REVIEW.md) - this module used to have
its own separate implementation that always failed open on a limiter error.
"""

from common.ratelimiting.decorators import graphql_ratelimit as ratelimit  # noqa: F401


def ip_throttle_rate(group, request) -> str:
    return "60/min"
