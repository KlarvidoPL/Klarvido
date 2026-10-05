"""
Tests for SSO email domain ownership verification (DNS TXT record).
"""

from types import SimpleNamespace
from unittest import mock

import dns.resolver
import pytest
from graphql import GraphQLError
from graphql_relay import to_global_id
from rest_framework import serializers as drf_serializers

from apps.multitenancy.constants import TenantType
from apps.multitenancy.tests.factories import TenantFactory
from apps.sso import constants
from apps.sso.models import SSOAuditLog, TenantDomain
from apps.sso.schema import (
    AddSSODomainMutation,
    DeleteSSODomainMutation,
    Query,
    VerifySSODomainMutation,
)
from apps.sso.serializers import (
    ActivateSSOConnectionSerializer,
    TenantSSOConnectionSerializer,
    UpdateTenantSSOConnectionSerializer,
)
from apps.sso.services import domain_verification as dv
from apps.sso.services.account_linking import AccountLinkingError, is_email_domain_allowed
from apps.sso.services.provisioning import JITProvisioningService
from apps.users.tests.factories import UserFactory

from . import factories

pytestmark = pytest.mark.django_db

VERIFIED = constants.SSODomainStatus.VERIFIED
PENDING = constants.SSODomainStatus.PENDING


@pytest.fixture
def org():
    return TenantFactory(type=TenantType.ORGANIZATION)


@pytest.fixture
def other_org():
    return TenantFactory(type=TenantType.ORGANIZATION)


def _unverified_connection(tenant, domain="client.pl"):
    """A connection whose domain is listed but not verified (the factory verifies by default)."""
    connection = factories.TenantSSOConnectionFactory(
        tenant=tenant,
        allowed_domains=[domain],
        status=constants.SSOConnectionStatus.DRAFT,
    )
    TenantDomain.objects.filter(tenant=tenant, domain=domain).delete()
    return connection


class TestNormalizeDomain:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("Example.COM", "example.com"),
            ("  example.com  ", "example.com"),
            ("example.com.", "example.com"),
            ("@example.com", "example.com"),
            ("sub.example.co.uk", "sub.example.co.uk"),
            ("zażółć.pl", "xn--za-6ja4f8n1l.pl"),
        ],
    )
    def test_accepts_plain_domains(self, raw, expected):
        assert dv.normalize_domain(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "localhost",
            "https://example.com",
            "example.com/path",
            "example.com:443",
            "*.example.com",
            "user@example.com",
            "exa mple.com",
            "-bad.example.com",
            "bad-.example.com",
            "a..example.com",
            "10.0.0.1",
            "x" * 64 + ".com",
        ],
    )
    def test_rejects_anything_that_is_not_a_domain(self, raw):
        with pytest.raises(dv.DomainVerificationError) as exc:
            dv.normalize_domain(raw)
        assert exc.value.code == dv.INVALID_DOMAIN_CODE


class TestAddDomain:
    def test_claim_starts_pending_with_a_token(self, org):
        claim = dv.add_domain(org, "Client.PL")

        assert claim.domain == "client.pl"
        assert claim.status == PENDING
        assert claim.verification_token
        assert claim.verification_record_value == f"klarvido-domain-verification={claim.verification_token}"

    @pytest.mark.parametrize("domain", ["gmail.com", "GMAIL.com", "wp.pl", "outlook.com"])
    def test_public_email_domains_are_refused(self, org, domain):
        with pytest.raises(dv.DomainVerificationError) as exc:
            dv.add_domain(org, domain)

        assert exc.value.code == dv.PUBLIC_DOMAIN_CODE
        assert not TenantDomain.objects.filter(tenant=org).exists()

    def test_adding_the_same_domain_twice_returns_the_existing_claim(self, org):
        first = dv.add_domain(org, "client.pl")
        second = dv.add_domain(org, "client.pl")

        assert first.pk == second.pk

    def test_domain_verified_by_another_organization_is_refused(self, org, other_org):
        dv.add_domain(other_org, "client.pl")
        TenantDomain.objects.filter(tenant=other_org, domain="client.pl").update(status=VERIFIED)

        with pytest.raises(dv.DomainVerificationError) as exc:
            dv.add_domain(org, "client.pl")

        assert exc.value.code == dv.DOMAIN_TAKEN_CODE

    def test_pending_claim_by_another_organization_does_not_block(self, org, other_org):
        dv.add_domain(other_org, "client.pl")

        claim = dv.add_domain(org, "client.pl")

        assert claim.tenant == org
        assert claim.status == PENDING


class TestVerifyDomain:
    def _claim(self, org, domain="client.pl"):
        return dv.add_domain(org, domain)

    def test_matching_txt_record_verifies_the_domain(self, org):
        claim = self._claim(org)
        with mock.patch.object(dv, "lookup_txt_records", return_value=[claim.verification_record_value]):
            verified = dv.verify_domain(claim)

        verified.refresh_from_db()
        assert verified.status == VERIFIED
        assert verified.verified_at is not None

    def test_record_among_other_txt_records_is_accepted(self, org):
        claim = self._claim(org)
        records = ["v=spf1 include:_spf.example.net ~all", claim.verification_record_value]
        with mock.patch.object(dv, "lookup_txt_records", return_value=records):
            dv.verify_domain(claim)

        claim.refresh_from_db()
        assert claim.status == VERIFIED

    def test_missing_record_is_refused(self, org):
        claim = self._claim(org)
        with mock.patch.object(dv, "lookup_txt_records", return_value=["v=spf1 -all"]):
            with pytest.raises(dv.DomainVerificationError) as exc:
                dv.verify_domain(claim)

        assert exc.value.code == dv.DNS_RECORD_NOT_FOUND_CODE
        claim.refresh_from_db()
        assert claim.status == PENDING

    def test_stale_token_is_refused(self, org):
        claim = self._claim(org)
        with mock.patch.object(dv, "lookup_txt_records", return_value=["klarvido-domain-verification=old-token"]):
            with pytest.raises(dv.DomainVerificationError):
                dv.verify_domain(claim)

    def test_lookup_returns_nothing_for_missing_domain(self):
        with mock.patch.object(dv.dns.resolver, "resolve", side_effect=dns.resolver.NXDOMAIN()):
            assert dv.lookup_txt_records("does-not-exist.example") == []

    def test_lookup_joins_split_txt_strings(self):
        rdata = mock.Mock(strings=[b"klarvido-domain-verification=", b"abc"])
        with mock.patch.object(dv.dns.resolver, "resolve", return_value=[rdata]):
            assert dv.lookup_txt_records("client.pl") == ["klarvido-domain-verification=abc"]

    def test_already_verified_domain_is_returned_without_dns(self, org):
        claim = self._claim(org)
        claim.status = VERIFIED
        claim.save()
        with mock.patch.object(dv, "lookup_txt_records") as lookup:
            dv.verify_domain(claim)

        lookup.assert_not_called()

    def test_domain_verified_elsewhere_meanwhile_is_refused(self, org, other_org):
        claim = self._claim(org)
        TenantDomain.objects.create(tenant=other_org, domain="client.pl", status=VERIFIED)
        with mock.patch.object(dv, "lookup_txt_records", return_value=[claim.verification_record_value]):
            with pytest.raises(dv.DomainVerificationError) as exc:
                dv.verify_domain(claim)

        assert exc.value.code == dv.DOMAIN_TAKEN_CODE

    def test_database_guards_one_verified_owner_per_domain(self, org, other_org):
        TenantDomain.objects.create(tenant=org, domain="client.pl", status=VERIFIED)

        from django.db import IntegrityError, transaction

        with pytest.raises(IntegrityError), transaction.atomic():
            TenantDomain.objects.create(tenant=other_org, domain="client.pl", status=VERIFIED)

    def test_dev_bypass_works_in_debug_only(self, org, settings):
        claim = self._claim(org)
        settings.SSO_DOMAIN_VERIFICATION_SKIP_DNS = True

        settings.DEBUG = True
        with mock.patch.object(dv.dns.resolver, "resolve") as resolve:
            dv.verify_domain(claim)
        resolve.assert_not_called()
        claim.refresh_from_db()
        assert claim.status == VERIFIED

    def test_dev_bypass_is_ignored_outside_debug(self, org, settings):
        claim = self._claim(org)
        settings.SSO_DOMAIN_VERIFICATION_SKIP_DNS = True
        settings.DEBUG = False

        with mock.patch.object(dv, "lookup_txt_records", return_value=[]):
            with pytest.raises(dv.DomainVerificationError):
                dv.verify_domain(claim)

        claim.refresh_from_db()
        assert claim.status == PENDING


class TestRemoveDomain:
    def test_removing_a_domain_used_by_a_connection_is_refused(self, org):
        factories.TenantSSOConnectionFactory(tenant=org, allowed_domains=["client.pl"])
        claim = TenantDomain.objects.get(tenant=org, domain="client.pl")

        with pytest.raises(dv.DomainVerificationError) as exc:
            dv.remove_domain(claim)

        assert exc.value.code == dv.DOMAIN_IN_USE_CODE
        assert TenantDomain.objects.filter(pk=claim.pk).exists()

    def test_unused_domain_can_be_removed(self, org):
        claim = dv.add_domain(org, "unused.pl")

        dv.remove_domain(claim)

        assert not TenantDomain.objects.filter(pk=claim.pk).exists()


class TestActivationGate:
    def _activate(self, connection):
        serializer = ActivateSSOConnectionSerializer(
            data={"id": str(connection.pk), "tenant_id": str(connection.tenant_id)}
        )
        serializer.is_valid(raise_exception=True)
        return serializer

    def test_activation_refused_while_a_domain_is_unverified(self, org):
        connection = _unverified_connection(org, "client.pl")

        with pytest.raises(drf_serializers.ValidationError) as exc:
            self._activate(connection)

        assert exc.value.detail["allowed_domains"][0] == dv.DOMAINS_NOT_VERIFIED_CODE

    def test_activation_refused_without_domains(self, org):
        connection = factories.TenantSSOConnectionFactory(tenant=org, allowed_domains=[])

        with pytest.raises(drf_serializers.ValidationError) as exc:
            self._activate(connection)

        assert exc.value.detail["allowed_domains"][0] == dv.NO_DOMAINS_CODE

    def test_activation_allowed_when_every_domain_is_verified(self, org):
        connection = factories.TenantSSOConnectionFactory(tenant=org, allowed_domains=["client.pl"])

        serializer = self._activate(connection)

        assert serializer.validated_data["connection"].pk == connection.pk

    def test_active_connection_cannot_add_an_unverified_domain(self, org):
        connection = factories.TenantSSOConnectionFactory(
            tenant=org, allowed_domains=["client.pl"], status=constants.SSOConnectionStatus.ACTIVE
        )
        serializer = UpdateTenantSSOConnectionSerializer(
            instance=connection, data={"allowed_domains": ["client.pl", "new.pl"]}, partial=True
        )

        assert not serializer.is_valid()
        assert serializer.errors["allowed_domains"][0] == dv.DOMAINS_NOT_VERIFIED_CODE

    def test_status_cannot_be_set_through_the_connection_serializer(self):
        assert "status" in TenantSSOConnectionSerializer.Meta.read_only_fields


class TestEnforcementOnlyForVerifiedDomains:
    def test_jit_refuses_an_unverified_domain(self, org):
        connection = _unverified_connection(org, "client.pl")

        assert not is_email_domain_allowed(connection, "jan@client.pl")

        with pytest.raises(AccountLinkingError):
            JITProvisioningService(connection).provision_or_update_user(idp_user_id="sub-1", email="jan@client.pl")

    def test_jit_accepts_a_verified_domain(self, org):
        connection = factories.TenantSSOConnectionFactory(tenant=org, allowed_domains=["client.pl"])

        assert is_email_domain_allowed(connection, "jan@client.pl")

    def test_claim_by_another_organization_does_not_route_users(self, org, other_org):
        factories.TenantSSOConnectionFactory(
            tenant=org,
            allowed_domains=["client.pl"],
            status=constants.SSOConnectionStatus.ACTIVE,
        )
        TenantDomain.objects.filter(tenant=org, domain="client.pl").update(status=PENDING)
        other_connection = factories.TenantSSOConnectionFactory(
            tenant=other_org,
            allowed_domains=["client.pl"],
            status=constants.SSOConnectionStatus.ACTIVE,
        )
        TenantDomain.objects.filter(tenant=other_org, domain="client.pl").update(status=VERIFIED)

        result = Query.resolve_sso_discover(None, None, "jan@client.pl")

        assert result["sso_available"] is True
        assert [c["id"] for c in result["connections"]] == [str(other_connection.pk)]

    def test_discovery_hides_an_unverified_domain(self, org):
        factories.TenantSSOConnectionFactory(
            tenant=org,
            allowed_domains=["client.pl"],
            status=constants.SSOConnectionStatus.ACTIVE,
        )
        TenantDomain.objects.filter(tenant=org, domain="client.pl").update(status=PENDING)

        result = Query.resolve_sso_discover(None, None, "jan@client.pl")

        assert result == {"sso_available": False, "require_sso": False, "connections": []}

    def test_discovery_ignores_connections_without_domains(self, org):
        factories.TenantSSOConnectionFactory(
            tenant=org,
            allowed_domains=[],
            status=constants.SSOConnectionStatus.ACTIVE,
        )

        result = Query.resolve_sso_discover(None, None, "jan@client.pl")

        assert result["sso_available"] is False


class TestUserCreationRequiresVerifiedDomain:
    def test_existing_account_on_unverified_domain_is_not_linked(self, org):
        connection = _unverified_connection(org, "client.pl")
        user = UserFactory(email="jan@client.pl")

        with pytest.raises(AccountLinkingError):
            JITProvisioningService(connection).provision_or_update_user(idp_user_id="sub-2", email=user.email)


class TestDomainMutations:
    def _info(self, tenant, user):
        return SimpleNamespace(context=SimpleNamespace(tenant=tenant, user=user))

    def test_add_returns_pending_domain_and_writes_audit_entries(self, org):
        user = UserFactory()
        result = AddSSODomainMutation.mutate(None, self._info(org, user), tenant_id=str(org.pk), domain="client.pl")

        assert result.sso_domain.status == PENDING
        assert SSOAuditLog.objects.filter(tenant=org, event_type=constants.SSOAuditEventType.DOMAIN_ADDED).exists()

    def test_add_public_domain_returns_stable_error_code(self, org):
        user = UserFactory()
        with pytest.raises(GraphQLError) as exc:
            AddSSODomainMutation.mutate(None, self._info(org, user), tenant_id=str(org.pk), domain="gmail.com")

        assert str(exc.value) == dv.PUBLIC_DOMAIN_CODE

    def test_failed_verification_is_audited_as_unsuccessful(self, org):
        user = UserFactory()
        claim = dv.add_domain(org, "client.pl")
        global_id = to_global_id("TenantDomainType", claim.pk)

        with mock.patch.object(dv, "lookup_txt_records", return_value=[]):
            with pytest.raises(GraphQLError) as exc:
                VerifySSODomainMutation.mutate(None, self._info(org, user), id=global_id, tenant_id=str(org.pk))

        assert str(exc.value) == dv.DNS_RECORD_NOT_FOUND_CODE
        entry = SSOAuditLog.objects.get(tenant=org, event_type=constants.SSOAuditEventType.DOMAIN_VERIFIED)
        assert entry.success is False
        assert entry.error_message == dv.DNS_RECORD_NOT_FOUND_CODE

    def test_delete_domain_in_use_returns_error_code(self, org):
        user = UserFactory()
        factories.TenantSSOConnectionFactory(tenant=org, allowed_domains=["client.pl"])
        claim = TenantDomain.objects.get(tenant=org, domain="client.pl")
        global_id = to_global_id("TenantDomainType", claim.pk)

        with pytest.raises(GraphQLError) as exc:
            DeleteSSODomainMutation.mutate(None, self._info(org, user), id=global_id, tenant_id=str(org.pk))

        assert str(exc.value) == dv.DOMAIN_IN_USE_CODE
