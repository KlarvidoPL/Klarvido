"""
Email domain ownership for SSO.

An organization may only use an email domain for SSO, JIT provisioning, SCIM and enforcement after it has
proven it controls that domain by publishing a DNS TXT record. Without this, an organization could claim
a domain it does not own and pre-register accounts (or redirect sign-ins) for the real owner's users.
"""

import logging
from datetime import timedelta

import dns.exception
import dns.resolver
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.notifications import sender
from apps.sso import constants
from apps.sso.constants import Notification as SSONotification
from apps.multitenancy.constants import ActionActorType, ActionType
from apps.sso.models import SSOAuditLog, TenantDomain, TenantSSOConnection
from common.action_logging.service import log_action

logger = logging.getLogger(__name__)

DNS_TIMEOUT_SECONDS = 5
# A verified domain lapses after its record has been missing for this long (checked daily)
LAPSE_AFTER_FAILURES = timedelta(days=7)

# Public mail providers: anyone can register an address here, so no organization can prove ownership.
PUBLIC_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "outlook.com",
        "outlook.co.uk",
        "hotmail.com",
        "hotmail.co.uk",
        "hotmail.fr",
        "live.com",
        "live.co.uk",
        "msn.com",
        "yahoo.com",
        "yahoo.co.uk",
        "yahoo.fr",
        "ymail.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
        "pm.me",
        "gmx.com",
        "gmx.net",
        "gmx.de",
        "web.de",
        "mail.com",
        "zoho.com",
        "yandex.com",
        "yandex.ru",
        "mail.ru",
        "inbox.ru",
        "bk.ru",
        "list.ru",
        "wp.pl",
        "o2.pl",
        "onet.pl",
        "onet.eu",
        "interia.pl",
        "interia.eu",
        "op.pl",
        "tlen.pl",
        "poczta.fm",
        "vp.pl",
        "gazeta.pl",
        "autograf.pl",
        "orange.fr",
        "free.fr",
        "laposte.net",
        "sfr.fr",
        "libero.it",
        "virgilio.it",
        "t-online.de",
        "seznam.cz",
        "centrum.cz",
        "naver.com",
        "qq.com",
        "163.com",
        "126.com",
        "sina.com",
        "rediffmail.com",
    }
)

# Stable error codes, translated by the frontend (SSO / Domain / <code>).
PUBLIC_DOMAIN_CODE = "public_domain"
INVALID_DOMAIN_CODE = "invalid_domain"
DOMAIN_TAKEN_CODE = "domain_taken"
DNS_RECORD_NOT_FOUND_CODE = "dns_record_not_found"
DOMAIN_IN_USE_CODE = "domain_in_use"
NO_DOMAINS_CODE = "no_domains"
DOMAINS_NOT_VERIFIED_CODE = "domains_not_verified"


class DomainVerificationError(ValueError):
    """A domain operation was refused. ``code`` is a stable, translatable identifier."""

    def __init__(self, code: str, details: dict | None = None):
        super().__init__(code)
        self.code = code
        # Extra context for the UI (e.g. which connections block a removal); never contains secrets
        self.details = details or {}


def normalize_domain(raw: str) -> str:
    """
    Return the canonical form of a domain typed by an admin (lowercase ASCII/IDNA, no trailing dot).
    Raises DomainVerificationError for anything that is not a plain registrable domain name.
    """
    value = (raw or "").strip().lower().rstrip(".")
    if value.startswith("@"):
        value = value[1:]
    if not value or "/" in value or ":" in value or "*" in value or " " in value or "@" in value:
        raise DomainVerificationError(INVALID_DOMAIN_CODE)
    try:
        value = value.encode("idna").decode("ascii")
    except UnicodeError:
        raise DomainVerificationError(INVALID_DOMAIN_CODE)

    labels = value.split(".")
    if len(labels) < 2 or len(value) > 253:
        raise DomainVerificationError(INVALID_DOMAIN_CODE)
    for label in labels:
        if not label or len(label) > 63 or label.startswith("-") or label.endswith("-"):
            raise DomainVerificationError(INVALID_DOMAIN_CODE)
        if not all(ch.isalnum() or ch == "-" for ch in label):
            raise DomainVerificationError(INVALID_DOMAIN_CODE)
    if labels[-1].isdigit():
        # An IPv4 address such as 10.0.0.1 is not a domain
        raise DomainVerificationError(INVALID_DOMAIN_CODE)
    return value


def is_public_email_domain(domain: str) -> bool:
    return domain in PUBLIC_EMAIL_DOMAINS


def get_verified_domains(tenant) -> set:
    """Domains this tenant has proven it owns."""
    return set(
        TenantDomain.objects.filter(tenant=tenant, status=constants.SSODomainStatus.VERIFIED).values_list(
            "domain", flat=True
        )
    )


def get_verified_tenant_id_for_domain(domain: str):
    """The tenant that has verified this domain, or None. A verified domain belongs to one tenant only."""
    return (
        TenantDomain.objects.filter(domain=domain, status=constants.SSODomainStatus.VERIFIED)
        .values_list("tenant_id", flat=True)
        .first()
    )


def check_claimable(tenant, raw_domain: str) -> str:
    """
    Raise DomainVerificationError if the tenant could not claim this domain (invalid, public, or verified
    by another organization). Returns the normalized domain. Used to reject a connection before it is saved.
    """
    domain = normalize_domain(raw_domain)
    if is_public_email_domain(domain):
        raise DomainVerificationError(PUBLIC_DOMAIN_CODE)
    if (
        TenantDomain.objects.filter(domain=domain, status=constants.SSODomainStatus.VERIFIED)
        .exclude(tenant=tenant)
        .exists()
    ):
        raise DomainVerificationError(DOMAIN_TAKEN_CODE)
    return domain


def claim_domains(tenant, raw_domains) -> None:
    """Add every domain the connection lists to the tenant's verification list as a pending claim."""
    for raw_domain in raw_domains or []:
        add_domain(tenant, raw_domain)


def add_domain(tenant, raw_domain: str) -> TenantDomain:
    """Claim a domain for a tenant. The claim stays pending until the TXT record is verified."""
    domain = normalize_domain(raw_domain)
    if is_public_email_domain(domain):
        raise DomainVerificationError(PUBLIC_DOMAIN_CODE)

    existing = TenantDomain.objects.filter(tenant=tenant, domain=domain).first()
    if existing is not None:
        return existing

    if (
        TenantDomain.objects.filter(domain=domain, status=constants.SSODomainStatus.VERIFIED)
        .exclude(tenant=tenant)
        .exists()
    ):
        raise DomainVerificationError(DOMAIN_TAKEN_CODE)

    return TenantDomain.objects.create(tenant=tenant, domain=domain)


def dns_check_bypassed() -> bool:
    """Development-only bypass. SECURITY: never honoured outside DEBUG, so production always checks DNS."""
    return bool(settings.DEBUG and getattr(settings, "SSO_DOMAIN_VERIFICATION_SKIP_DNS", False))


def lookup_txt_records(name: str):
    """
    TXT records published at ``name``, each joined into one string.
    Returns [] when the name does not exist, and None when DNS could not be queried (timeout, SERVFAIL).
    """
    try:
        answer = dns.resolver.resolve(name, "TXT", lifetime=DNS_TIMEOUT_SECONDS)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return []
    except dns.exception.DNSException:
        logger.warning("SSO domain verification DNS lookup failed for %s", name, exc_info=True)
        return None
    return [b"".join(rdata.strings).decode("utf-8", errors="replace") for rdata in answer]


def record_present(tenant_domain: TenantDomain):
    """
    True if the verification value is published on the challenge subdomain or on the apex,
    False if it is missing, None if DNS could not be queried.
    The apex is accepted so claims made before the subdomain existed keep working.
    """
    expected = tenant_domain.verification_record_value
    unknown = False
    for name in (tenant_domain.verification_record_name, tenant_domain.domain):
        records = lookup_txt_records(name)
        if records is None:
            unknown = True
        elif expected in records:
            return True
    return None if unknown else False


def verify_domain(tenant_domain: TenantDomain) -> TenantDomain:
    """
    Check the TXT record and mark the domain verified. Refused if the record is missing or if another
    tenant verified the domain in the meantime. Also re-verifies a lapsed domain.
    """
    if tenant_domain.is_verified:
        return tenant_domain

    if not dns_check_bypassed() and record_present(tenant_domain) is not True:
        raise DomainVerificationError(DNS_RECORD_NOT_FOUND_CODE)

    try:
        with transaction.atomic():
            if (
                TenantDomain.objects.filter(domain=tenant_domain.domain, status=constants.SSODomainStatus.VERIFIED)
                .exclude(pk=tenant_domain.pk)
                .exists()
            ):
                raise DomainVerificationError(DOMAIN_TAKEN_CODE)
            tenant_domain.status = constants.SSODomainStatus.VERIFIED
            tenant_domain.verified_at = timezone.now()
            tenant_domain.consecutive_failures = 0
            tenant_domain.last_checked_at = tenant_domain.verified_at
            tenant_domain.save(
                update_fields=["status", "verified_at", "consecutive_failures", "last_checked_at", "updated_at"]
            )
    except IntegrityError:
        # The partial unique index on verified domains caught a concurrent verification
        raise DomainVerificationError(DOMAIN_TAKEN_CODE)
    return tenant_domain


def recheck_domain(tenant_domain: TenantDomain) -> str:
    """
    Re-check a verified domain's TXT record. A missing record starts a grace period: the owners are
    warned on the first failed check, and the domain lapses once the record has been missing for
    LAPSE_AFTER_FAILURES (seven days). Found again, the grace period resets. DNS errors change nothing,
    so a resolver outage can never lock a company out. Returns the resulting status.
    """
    if tenant_domain.status != constants.SSODomainStatus.VERIFIED:
        return tenant_domain.status

    present = record_present(tenant_domain)
    now = timezone.now()
    tenant_domain.last_checked_at = now
    if present is None:
        tenant_domain.save(update_fields=["last_checked_at", "updated_at"])
        return tenant_domain.status

    if present:
        tenant_domain.consecutive_failures = 0
        tenant_domain.first_failed_at = None
        tenant_domain.save(update_fields=["last_checked_at", "consecutive_failures", "first_failed_at", "updated_at"])
        return tenant_domain.status

    tenant_domain.consecutive_failures += 1
    if tenant_domain.first_failed_at is None:
        tenant_domain.first_failed_at = now
        tenant_domain.save(update_fields=["last_checked_at", "consecutive_failures", "first_failed_at", "updated_at"])
        _notify_record_missing(tenant_domain)
    elif now - tenant_domain.first_failed_at >= LAPSE_AFTER_FAILURES:
        _lapse_domain(tenant_domain)
    else:
        tenant_domain.save(update_fields=["last_checked_at", "consecutive_failures", "updated_at"])
    return tenant_domain.status


def _lapse_domain(tenant_domain: TenantDomain) -> None:
    """
    Stop trusting a domain whose record disappeared: connections that list it are deactivated (their
    configuration is kept), and the change is recorded in the SSO audit log and the Activity Log.
    Existing memberships are not removed.
    """
    tenant_domain.status = constants.SSODomainStatus.LAPSED
    tenant_domain.save(update_fields=["status", "last_checked_at", "consecutive_failures", "updated_at"])

    deactivated = []
    for connection in TenantSSOConnection.objects.select_related("created_by").filter(
        tenant=tenant_domain.tenant, status=constants.SSOConnectionStatus.ACTIVE
    ):
        if tenant_domain.domain in (connection.allowed_domains or []):
            connection.status = constants.SSOConnectionStatus.INACTIVE
            connection.save(update_fields=["status", "updated_at"])
            deactivated.append(connection)

    connection_names = [connection.name for connection in deactivated]
    description = f"Domain {tenant_domain.domain} lapsed: its verification record is missing."
    if connection_names:
        description += " Deactivated connections: " + ", ".join(connection_names) + "."
    SSOAuditLog.log_event(
        event_type=constants.SSOAuditEventType.DOMAIN_LAPSED,
        tenant=tenant_domain.tenant,
        description=description,
        metadata={"domain": tenant_domain.domain, "deactivated_connections": connection_names},
        success=False,
    )
    log_action(
        tenant_id=tenant_domain.tenant_id,
        action_type=ActionType.DEACTIVATE,
        entity_type="sso_domain",
        entity_id=str(tenant_domain.pk),
        entity_name=tenant_domain.domain,
        actor_type=ActionActorType.SYSTEM_SCHEDULED,
        changes={"status": {"old": constants.SSODomainStatus.VERIFIED, "new": constants.SSODomainStatus.LAPSED}},
    )
    _notify_domain_lapsed(tenant_domain, deactivated)


def _notify_domain_lapsed(tenant_domain: TenantDomain, deactivated_connections) -> None:
    """
    Tell the tenant owners, and whoever configured each deactivated connection, that the domain lapsed.
    Each person gets one notification, even when they are both an owner and a connection's creator.
    """
    recipients = {}
    for owner in tenant_domain.tenant.owners:
        recipients[owner.pk] = owner
    for connection in deactivated_connections:
        if connection.created_by is not None:
            recipients[connection.created_by.pk] = connection.created_by

    data = {
        "domain": tenant_domain.domain,
        "tenant_name": tenant_domain.tenant.name,
        "connection_names": [connection.name for connection in deactivated_connections],
    }
    _send_to(recipients.values(), SSONotification.SSO_DOMAIN_LAPSED, data)


def _notify_record_missing(tenant_domain: TenantDomain) -> None:
    """Warn the tenant owners on the first failed check, while there is still time to restore the record."""
    data = {
        "domain": tenant_domain.domain,
        "tenant_name": tenant_domain.tenant.name,
        "grace_days": LAPSE_AFTER_FAILURES.days,
    }
    _send_to(tenant_domain.tenant.owners, SSONotification.SSO_DOMAIN_RECORD_MISSING, data)


def _send_to(users, notification, data) -> None:
    for user in users:
        try:
            sender.send_notification(user=user, type=notification.value, data=data, issuer=None)
        except Exception:
            # A notification failure must not undo a lapse or stop the other recipients
            logger.warning("Failed to send SSO domain notification %s", notification.value, exc_info=True)


def remove_domain(tenant_domain: TenantDomain) -> None:
    """
    Remove a domain claim. Refused while an SSO connection of the tenant still lists the domain, so an
    active connection can never silently lose a domain it depends on.
    """
    connections = TenantSSOConnection.objects.filter(tenant=tenant_domain.tenant)
    blocking = [
        connection.name for connection in connections if tenant_domain.domain in (connection.allowed_domains or [])
    ]
    if blocking:
        raise DomainVerificationError(DOMAIN_IN_USE_CODE, {"connection_names": blocking})
    tenant_domain.delete()


def ensure_connection_domains_verified(connection) -> None:
    """Activation gate: a connection needs at least one domain, and every domain it lists must be verified."""
    domains = [d for d in (connection.allowed_domains or []) if d]
    if not domains:
        raise DomainVerificationError(NO_DOMAINS_CODE)
    verified = get_verified_domains(connection.tenant)
    if any(domain.lower() not in verified for domain in domains):
        raise DomainVerificationError(DOMAINS_NOT_VERIFIED_CODE)
