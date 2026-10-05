"""
Email domain ownership for SSO.

An organization may only use an email domain for SSO, JIT provisioning, SCIM and enforcement after it has
proven it controls that domain by publishing a DNS TXT record. Without this, an organization could claim
a domain it does not own and pre-register accounts (or redirect sign-ins) for the real owner's users.
"""

import logging

import dns.exception
import dns.resolver
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.sso import constants
from apps.sso.models import TenantDomain, TenantSSOConnection

logger = logging.getLogger(__name__)

DNS_TIMEOUT_SECONDS = 5

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

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


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


def _dns_bypass_enabled() -> bool:
    # SECURITY: never honoured outside DEBUG, so production always checks DNS.
    return bool(settings.DEBUG and getattr(settings, "SSO_DOMAIN_VERIFICATION_SKIP_DNS", False))


def lookup_txt_records(domain: str) -> list:
    """All TXT records published on the domain, each joined into one string."""
    try:
        answer = dns.resolver.resolve(domain, "TXT", lifetime=DNS_TIMEOUT_SECONDS)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
        return []
    except dns.exception.DNSException:
        logger.warning("SSO domain verification DNS lookup failed for %s", domain, exc_info=True)
        return []
    return [b"".join(rdata.strings).decode("utf-8", errors="replace") for rdata in answer]


def verify_domain(tenant_domain: TenantDomain) -> TenantDomain:
    """
    Check the TXT record and mark the domain verified. Refused if the record is missing or if another
    tenant verified the domain in the meantime.
    """
    if tenant_domain.is_verified:
        return tenant_domain

    if not _dns_bypass_enabled():
        expected = tenant_domain.verification_record_value
        if expected not in lookup_txt_records(tenant_domain.domain):
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
            tenant_domain.save(update_fields=["status", "verified_at", "updated_at"])
    except IntegrityError:
        # The partial unique index on verified domains caught a concurrent verification
        raise DomainVerificationError(DOMAIN_TAKEN_CODE)
    return tenant_domain


def remove_domain(tenant_domain: TenantDomain) -> None:
    """
    Remove a domain claim. Refused while an SSO connection of the tenant still lists the domain, so an
    active connection can never silently lose a domain it depends on.
    """
    connections = TenantSSOConnection.objects.filter(tenant=tenant_domain.tenant)
    if any(tenant_domain.domain in (connection.allowed_domains or []) for connection in connections):
        raise DomainVerificationError(DOMAIN_IN_USE_CODE)
    tenant_domain.delete()


def ensure_connection_domains_verified(connection) -> None:
    """Activation gate: a connection needs at least one domain, and every domain it lists must be verified."""
    domains = [d for d in (connection.allowed_domains or []) if d]
    if not domains:
        raise DomainVerificationError(NO_DOMAINS_CODE)
    verified = get_verified_domains(connection.tenant)
    if any(domain.lower() not in verified for domain in domains):
        raise DomainVerificationError(DOMAINS_NOT_VERIFIED_CODE)
