"""
Rules for attaching an identity-provider account to a Klarvido user.

Every organization can configure its own identity provider (SSO or SCIM), and that identity
provider can assert any email address. A Klarvido account is global (it can belong to several
organizations), so an organization must never be able to take over an account just by asserting
its email. These rules are shared by JIT provisioning (SAML/OIDC login) and SCIM.
"""

from apps.multitenancy.constants import TenantType
from apps.multitenancy.models import TenantMembership

# Error messages are matched by apps.sso.security.get_safe_error_code; keep the wording in sync.
DOMAIN_NOT_ALLOWED_MESSAGE = "Email domain is not allowed for this SSO connection."
ACCOUNT_NOT_MEMBER_MESSAGE = "Existing account is not a member of this organization."
PRIVILEGED_ACCOUNT_MESSAGE = "Existing account is not a member of this organization (privileged account)."


class AccountLinkingError(ValueError):
    """An identity-provider account must not be attached to this Klarvido user."""


def is_email_domain_allowed(connection, email: str) -> bool:
    """The email's domain must be listed on the connection. An empty list allows no domain."""
    if not email or "@" not in email:
        return False
    domain = email.rsplit("@", 1)[-1].strip().lower()
    allowed = {d.strip().lower() for d in (connection.allowed_domains or []) if d}
    return domain in allowed


def ensure_domain_allowed(connection, email: str) -> None:
    if not is_email_domain_allowed(connection, email):
        raise AccountLinkingError(DOMAIN_NOT_ALLOWED_MESSAGE)


def ensure_can_link_existing_user(user, tenant) -> None:
    """An existing account can only be attached if it is already an accepted member of this organization.

    Pending invitations do not count: otherwise an organization could invite any email and then assert
    that email from its own identity provider to take over the account.

    Platform superusers are never attached through an identity provider: their accounts reach every
    organization, so a single organization's identity provider must not be able to sign them in.
    """
    if user.is_superuser:
        raise AccountLinkingError(PRIVILEGED_ACCOUNT_MESSAGE)
    if not TenantMembership.objects.filter(user=user, tenant=tenant).exists():
        raise AccountLinkingError(ACCOUNT_NOT_MEMBER_MESSAGE)


def ensure_can_use_linked_user(user) -> None:
    """Accounts linked before these rules existed must still never sign in a superuser."""
    if user.is_superuser:
        raise AccountLinkingError(PRIVILEGED_ACCOUNT_MESSAGE)


def is_user_managed_only_by(user, tenant) -> bool:
    """True if the account belongs to no organization other than this one.

    Only then may this organization's identity provider overwrite account-wide data such as the
    profile name. Personal (default) tenants are ignored.
    """
    return (
        not TenantMembership.objects.filter(user=user, tenant__type=TenantType.ORGANIZATION)
        .exclude(tenant=tenant)
        .exists()
    )
