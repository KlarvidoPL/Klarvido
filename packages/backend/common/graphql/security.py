"""
GraphQL Security Middleware

This module provides security-related middleware for GraphQL operations.
"""

import logging
from inspect import isawaitable

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied, ValidationError as DjangoValidationError
from django.http import Http404
from promise import Promise
from rest_framework.exceptions import APIException
from sentry_sdk import capture_exception

from common.exceptions import DomainException

from django.conf import settings
from graphql.error import GraphQLError

logger = logging.getLogger(__name__)


class DisableIntrospectionMiddleware:
    """
    Middleware to disable GraphQL introspection in non-debug environments.

    SECURITY: GraphQL introspection exposes the entire API schema, which can
    help attackers understand the API structure and find potential vulnerabilities.
    This middleware blocks introspection queries in production.

    In DEBUG mode, introspection is allowed for development convenience.

    Usage:
        Add to GRAPHENE["MIDDLEWARE"] in settings.py:
        GRAPHENE = {
            "MIDDLEWARE": [
                "common.graphql.security.DisableIntrospectionMiddleware",
                ...
            ],
        }
    """

    # NOTE: __typename is NOT blocked - it's a meta field used by Apollo Client
    # for type resolution and cache normalization. Only block true introspection.
    INTROSPECTION_FIELDS = {"__schema", "__type"}
    INTROSPECTION_ERROR = "GraphQL introspection is disabled in production."

    def resolve(self, next, root, info, **args):
        """
        Check if the query is an introspection query and block it in production.

        Args:
            next: The next resolver in the middleware chain
            root: The root value
            info: GraphQL ResolveInfo object
            **args: Additional arguments

        Returns:
            The result of the next resolver, or raises GraphQLError for introspection

        Raises:
            GraphQLError: If introspection is attempted in production
        """
        # Allow introspection in DEBUG mode
        if settings.DEBUG:
            return next(root, info, **args)

        # Check if this is an introspection query
        field_name = info.field_name.lower() if info.field_name else ""
        if field_name in self.INTROSPECTION_FIELDS:
            raise GraphQLError(self.INTROSPECTION_ERROR)

        return next(root, info, **args)


GENERIC_ERROR = "An error occurred while processing your request."
SAFE_GRAPHQL_MESSAGES = frozenset(
    {
        GENERIC_ERROR,
        "permission_denied",
        "You do not have permission to perform this action.",
        "You don't have permission to access this resource",
        "Permission denied",
        "Permission denied. Admin access required.",
        "Authentication required for notifications subscription",
        "Invalid translations format. Expected JSON object.",
        "Version not found",
        "Invalid GraphQL document",
        "Only subscriptions are allowed over WebSocket; send queries and mutations over HTTP",
        DisableIntrospectionMiddleware.INTROSPECTION_ERROR,
    }
)


def sanitize_graphql_error(error, *, request_error=False):
    """Allow intentional client errors; never trust exception names or message prefixes."""
    if settings.DEBUG:
        return error
    original = getattr(error, "original_error", None)
    cause = original or error
    # Inspect the cause, rather than trusting a wrapper's potentially misleading message.
    while getattr(cause, "original_error", None) is not None:
        cause = cause.original_error
    safe = isinstance(cause, (DomainException, DjangoValidationError, DjangoPermissionDenied, Http404))
    safe = safe or (isinstance(cause, APIException) and cause.status_code < 500)
    if safe:
        return error
    if isinstance(cause, GraphQLError):
        if cause.message in SAFE_GRAPHQL_MESSAGES:
            return error
        # Parsing, schema-validation and variable-coercion errors have no resolver cause.
        if request_error and getattr(error, "path", None) is None:
            return error
    capture_exception(cause)
    return GraphQLError(
        GENERIC_ERROR,
        nodes=getattr(error, "nodes", None),
        path=getattr(error, "path", None),
        extensions={"code": "internal_server_error"},
    )


class SanitizeErrorsMiddleware:
    """Protect resolver failures, including awaitables and legacy Promise resolvers."""

    GENERIC_ERROR = GENERIC_ERROR

    def on_error(self, error):
        raise sanitize_graphql_error(error)

    def resolve(self, next, root, info, **args):
        try:
            result = next(root, info, **args)
        except Exception as error:
            self.on_error(error)
        if isinstance(result, Promise):
            return result.catch(self.on_error)
        if isawaitable(result):

            async def await_result():
                try:
                    return await result
                except Exception as error:
                    self.on_error(error)

            return await_result()
        return result
