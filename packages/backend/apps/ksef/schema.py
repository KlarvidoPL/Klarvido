"""
GraphQL schema for the KSeF token of an organization.

Nothing here returns the token. Reads expose status metadata only; writes return a stable error code (never KSeF's raw
response text), which the frontend maps to translated messages.
"""

import graphene
from graphene_django import DjangoObjectType
from rest_framework.exceptions import PermissionDenied

from common.acl.policies import IsTenantMemberAccess
from common.graphql.acl import permission_classes, requires
from common.graphql.acl.decorators import PERMISSION_DENIED_MESSAGE
from common.ratelimiting import RateLimitKey, graphql_ratelimit

from . import models, services
from .constants import KsefErrorCode


def get_checked_tenant(info):
    """The organization resolved by the tenant middleware for an explicit tenantId the user is a member of."""
    tenant = getattr(info.context, "tenant", None)
    if not tenant:
        raise PermissionDenied(PERMISSION_DENIED_MESSAGE)
    return tenant


class KsefCredentialType(DjangoObjectType):
    """Metadata about the stored KSeF token. The token itself is intentionally not a field."""

    class Meta:
        model = models.KsefCredential
        fields = ("status", "token_hint", "token_name", "last_verified_at", "last_error_code", "updated_at")

    status = graphene.String()
    token_hint = graphene.String()
    token_name = graphene.String()
    last_error_code = graphene.String()


class KsefCredentialResult(graphene.ObjectType):
    ok = graphene.Boolean()
    error_code = graphene.String()
    ksef_credential = graphene.Field(KsefCredentialType)


def _result(result: services.CredentialResult) -> KsefCredentialResult:
    return KsefCredentialResult(
        ok=not result.error_code,
        error_code=result.error_code or None,
        ksef_credential=result.credential,
    )


class KsefQuery(graphene.ObjectType):
    ksef_credential = graphene.Field(
        KsefCredentialType,
        tenant_id=graphene.ID(required=True),
        description="KSeF token status for a tenant (never the token itself)",
    )

    @staticmethod
    @permission_classes(IsTenantMemberAccess, requires("security.ksef.view"))
    def resolve_ksef_credential(root, info, tenant_id, **kwargs):
        return services.get_credential(get_checked_tenant(info))


class SetKsefTokenMutation(graphene.Mutation):
    """Verify a KSeF token with KSeF, then store it encrypted. An invalid token is never stored."""

    class Arguments:
        tenant_id = graphene.ID(required=True)
        token = graphene.String(required=True)

    Output = KsefCredentialResult

    @classmethod
    @graphql_ratelimit(rate="5/min", key=RateLimitKey.USER)
    def mutate(cls, root, info, tenant_id, token):
        tenant = get_checked_tenant(info)
        return _result(services.save_token(tenant, info.context.user, token))


class TestKsefTokenMutation(graphene.Mutation):
    """Check the stored KSeF token with KSeF again."""

    class Arguments:
        tenant_id = graphene.ID(required=True)

    Output = KsefCredentialResult

    @classmethod
    @graphql_ratelimit(rate="10/min", key=RateLimitKey.USER)
    def mutate(cls, root, info, tenant_id):
        tenant = get_checked_tenant(info)
        return _result(services.retest_token(tenant, info.context.user))


class DeleteKsefTokenMutation(graphene.Mutation):
    class Arguments:
        tenant_id = graphene.ID(required=True)

    ok = graphene.Boolean()
    error_code = graphene.String()

    @classmethod
    def mutate(cls, root, info, tenant_id):
        tenant = get_checked_tenant(info)
        if not services.delete_token(tenant, info.context.user):
            return cls(ok=False, error_code=KsefErrorCode.NOT_CONFIGURED)
        return cls(ok=True)


# Changing the token also requires security.ksef.view: the card can only be used by roles that can see the connection.
KSEF_MANAGE = requires("security.ksef.view", "security.ksef.manage", mode="all")


class KsefMutation(graphene.ObjectType):
    set_ksef_token = permission_classes(IsTenantMemberAccess, KSEF_MANAGE)(SetKsefTokenMutation.Field())
    test_ksef_token = permission_classes(IsTenantMemberAccess, KSEF_MANAGE)(TestKsefTokenMutation.Field())
    delete_ksef_token = permission_classes(IsTenantMemberAccess, KSEF_MANAGE)(DeleteKsefTokenMutation.Field())
