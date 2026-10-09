import functools
from typing import Type, Callable

import graphene
from graphene.relay.node import NodeField
from graphene.types import Field
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.request import Request
from . import types

PERMISSION_DENIED_MESSAGE = "permission_denied"
NOT_AUTHENTICATED_MESSAGE = "not_authenticated"


def check_permissions(perms: types.PermissionsClasses, request: Request | dict, root):
    # Only subscriptions are accepted by the WebSocket consumer.
    if hasattr(request, "channels_scope"):
        return
    for permission_class in perms:
        if not permission_class().has_permission(request=request, view=root):
            # Distinguish "no session at all" (including one invalidated by a password
            # change - CHECK_REVOKE_TOKEN - but not yet naturally expired) from "authenticated
            # but genuinely lacks this permission". The frontend only attempts a silent
            # token-refresh-then-redirect-to-login recovery for the former; conflating the two
            # into one generic permission_denied previously left a stale second-browser session
            # showing a raw, untranslated error instead of being signed out.
            user = getattr(request, "user", None)
            if not user or not user.is_authenticated:
                raise NotAuthenticated(NOT_AUTHENTICATED_MESSAGE)
            raise PermissionDenied(PERMISSION_DENIED_MESSAGE)


def wraps_resolver_function(fn: Callable, perms: types.PermissionsClasses, node_resolver: bool = False) -> Callable:
    previous = getattr(fn, "_graphql_permissions", ())
    combined = tuple(dict.fromkeys((*previous, *perms)))
    original = getattr(fn, "_graphql_original_resolver", fn)

    if node_resolver:

        @functools.wraps(original)
        def wrapped(only_type, root, info, id):
            check_permissions(combined, info.context, root)
            return original(only_type, root, info, id)

    else:

        @functools.wraps(original)
        def wrapped(root, info, *args, **kwargs):
            check_permissions(combined, info.context, root)
            return original(root, info, *args, **kwargs)

    wrapped._graphql_permissions = combined
    wrapped._graphql_original_resolver = original
    return wrapped


class PermissionNodeField(NodeField):
    """Keep permissions local to this field, rather than mutating the shared Node class."""

    def wrap_resolve(self, parent_resolver):
        return wraps_resolver_function(super().wrap_resolve(parent_resolver), self._graphql_permissions)


def wraps_field(field: Field, perms: types.PermissionsClasses, parent_resolver=None) -> Field:
    if isinstance(field, NodeField):
        if not isinstance(field, PermissionNodeField) and not hasattr(field, "_graphql_permissions"):
            original_wrap_resolve = field.wrap_resolve

            def wrap_node_resolver(parent):
                return wraps_resolver_function(original_wrap_resolve(parent), field._graphql_permissions)

            field.wrap_resolve = wrap_node_resolver
        field._graphql_permissions = tuple(dict.fromkeys((*getattr(field, "_graphql_permissions", ()), *perms)))
    else:
        resolver = field.resolver or parent_resolver
        if resolver:
            field.resolver = wraps_resolver_function(resolver, perms)
    return field


def wraps_object_type(obj: Type[graphene.ObjectType], perms: types.PermissionsClasses, defaults=False):
    for field_name, field in obj._meta.fields.items():
        parent_resolver = getattr(obj, f"resolve_{field_name}", None)
        resolver = field.resolver or parent_resolver
        # Global defaults are a fallback; explicit public permissions intentionally replace them.
        if defaults and (getattr(resolver, "_graphql_permissions", ()) or getattr(field, "_graphql_permissions", ())):
            continue
        wraps_field(field, perms, parent_resolver)
    return obj
