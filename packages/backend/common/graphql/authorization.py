"""Object authorization shared by GraphQL lookups and relationship traversal."""

from django.core.exceptions import ValidationError
from graphene_django import DjangoObjectType
from graphql import GraphQLError
from graphql_relay import from_global_id

from apps.multitenancy.disabled_permissions import DISABLED_PERMISSION_CODES


def get_user(info):
    context = info.context
    scope = getattr(context, "channels_scope", {})
    return scope.get("user") or getattr(context, "user", None)


def authorization_cache(info):
    context = info.context
    operation = getattr(info, "operation", None)
    if not hasattr(context, "_graphql_authorization_cache") or (
        getattr(context, "_graphql_authorization_operation", None) is not operation
    ):
        context._graphql_authorization_operation = operation
        context._graphql_authorization_cache = {"objects": {}, "tenants": {}}
    return context._graphql_authorization_cache


def authorized_tenant(info, tenant_id, permission):
    """Authorize the submitted tenant before any operation or side effect."""
    from apps.multitenancy.middleware import get_current_tenant_with_membership_check
    from apps.multitenancy.models import user_has_permission

    user = get_user(info)
    if not user or not user.is_authenticated or not user.is_active:
        raise GraphQLError("permission_denied")
    type_name, pk = from_global_id(tenant_id)
    if type_name != "TenantType" or not pk:
        raise GraphQLError("permission_denied")
    tenant = get_current_tenant_with_membership_check(pk, user, info.context)
    if not tenant or not user_has_permission(user, tenant, permission):
        raise GraphQLError("permission_denied")
    return tenant


def tenant_ids(info, permission=None):
    from apps.multitenancy.middleware import get_current_tenant_with_membership_check
    from apps.multitenancy.models import Tenant, is_superuser_bypass_eligible, user_has_permission

    user = get_user(info)
    if not user or not user.is_authenticated or not user.is_active:
        return []
    path = getattr(info, "path", None)
    root_field = path.as_list()[0] if hasattr(path, "as_list") else None
    cache = authorization_cache(info)["tenants"]
    key = (root_field, str(user.pk), permission)
    if key in cache:
        return cache[key]
    tenants = (
        Tenant.objects.all()
        if is_superuser_bypass_eligible(user)
        else Tenant.objects.filter(user_memberships__user=user, user_memberships__is_accepted=True).distinct()
    )
    result = [
        tenant.pk
        for tenant in tenants
        if (
            get_current_tenant_with_membership_check(tenant.pk, user, info.context)
            and (permission is None or user_has_permission(user, tenant, permission))
        )
    ]
    cache[key] = result
    return result


def scope_queryset(queryset, info):
    """Unknown model types are denied until their ownership policy is registered."""
    label = queryset.model._meta.concrete_model._meta.label_lower
    user = get_user(info)
    if label == "translations.locale":
        return queryset.filter(is_active=True)
    if label in {"djstripe.product", "djstripe.price", "djstripe.plan"}:
        return queryset
    if not user or not user.is_authenticated or not user.is_active:
        return queryset.none()
    if label == "multitenancy.permission":
        return queryset.exclude(code__in=DISABLED_PERMISSION_CODES)
    if label == "content.demoitem":
        return queryset
    if label.startswith("translations."):
        return queryset if user.is_superuser else queryset.none()
    owner_fields = {
        "users.user": "pk",
        "users.userprofile": "user_id",
        "sso.userpasskey": "user_id",
        "sso.ssosession": "user_id",
        "sso.userdevice": "user_id",
        "notifications.notification": "user_id",
        "demo.documentdemoitem": "created_by_id",
        "demo.contentfuldemoitemfavorite": "user_id",
    }
    if label in owner_fields:
        return queryset.filter(**{owner_fields[label]: user.pk})
    if label == "multitenancy.tenant":
        return queryset.filter(pk__in=tenant_ids(info))
    if label == "multitenancy.tenantmembership":
        # Own pending invitations remain available through their existing dedicated flow.
        from django.db.models import Q

        return queryset.filter(Q(user=user) | Q(tenant_id__in=tenant_ids(info, "members.view")))
    if label == "multitenancy.tenantmembershiprole":
        return queryset.filter(membership__tenant_id__in=tenant_ids(info, "members.view"))
    permissions = {
        "demo.cruddemoitem": "features.crud.view",
        "multitenancy.organizationrole": "org.roles.view",
        "multitenancy.actionlog": "security.logs.view",
        "sso.ssoauditlog": "security.view",
        "multitenancy.actionlogexport": "security.logs.export",
        "backup.backupconfig": "backup.view",
        "backup.backuprecord": "backup.view",
        "backup.restorerecord": "backup.view",
        "ksef.ksefcredential": "security.ksef.view",
    }
    if label in permissions:
        return queryset.filter(tenant_id__in=tenant_ids(info, permissions[label]))
    if label.startswith("djstripe.") and any(field.name == "customer" for field in queryset.model._meta.fields):
        return queryset.filter(customer__subscriber_id__in=tenant_ids(info, "billing.view"))
    return queryset.none()


def model_queryset(model):
    # The membership manager normally hides pending invitations. Ownership checks
    # below explicitly allow the invitee to read their own pending record.
    if model._meta.label_lower == "multitenancy.tenantmembership":
        return model._default_manager.get_all()
    return model._default_manager.all()


class AuthorizedDjangoObjectType(DjangoObjectType):
    class Meta:
        abstract = True

    @classmethod
    def get_queryset(cls, queryset, info):
        return scope_queryset(queryset, info)

    @classmethod
    def get_node(cls, info, id):
        model = cls._meta.model
        identifiers = ["pk"]
        # dj-stripe relationships target the Stripe id, while Relay uses djstripe_id.
        if model._meta.app_label == "djstripe" and model._meta.pk.name != "id":
            identifiers.append("id")
        for identifier in identifiers:
            try:
                instance = cls.get_queryset(model_queryset(model).filter(**{identifier: id}), info).first()
            except (ValueError, TypeError, ValidationError):
                continue
            if instance is not None:
                return instance
        return None


class ObjectAuthorizationMiddleware:
    """Check objects before resolving fields, including manually resolved relationships."""

    def resolve(self, next, root, info, **args):
        graph_type = getattr(info.parent_type, "graphene_type", None)
        if root is not None and graph_type and issubclass(graph_type, DjangoObjectType):
            user = get_user(info)
            # These deliberately small user summaries are used for notification issuers.
            summary = (
                graph_type._meta.name == "UserType"
                and graph_type._meta.model._meta.label_lower == "users.user"
                and info.field_name
                in {
                    "id",
                    "email",
                    "firstName",
                    "lastName",
                    "avatar",
                }
            )
            cache = authorization_cache(info)["objects"]
            key = (graph_type, str(root.pk), info.path.prev)
            if key not in cache:
                cache[key] = scope_queryset(model_queryset(graph_type._meta.model).filter(pk=root.pk), info).exists()
            # Keep pending invitations usable by the common tenant query without
            # exposing settings or requiring access to the invited organization.
            pending_identity = False
            if (
                not cache[key]
                and graph_type._meta.model._meta.label_lower == "multitenancy.tenant"
                and user
                and user.is_authenticated
                and user.is_active
            ):
                from apps.multitenancy.models import TenantMembership

                pending_key = (*key, "pending")
                if pending_key not in cache:
                    cache[pending_key] = (
                        TenantMembership.objects.get_all().filter(tenant=root, user=user, is_accepted=False).exists()
                    )
                if cache[pending_key]:
                    pending_identity = info.field_name in {"id", "name", "slug", "type", "membership", "__typename"}
                    if not pending_identity:
                        return False if info.field_name in {"onboardingRequired", "onboardingCompleted"} else None
            if not (cache[key] or pending_identity or (summary and user and user.is_authenticated and user.is_active)):
                raise GraphQLError("permission_denied")
        return next(root, info, **args)
