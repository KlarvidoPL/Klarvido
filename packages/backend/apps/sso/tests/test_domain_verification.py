"""
Tests for SSO email domain ownership verification (DNS TXT record).
"""

from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

import dns.resolver
import pytest
from django.utils import timezone
from graphql import GraphQLError
from graphql_relay import to_global_id
from rest_framework import serializers as drf_serializers

from apps.multitenancy.constants import TenantType, TenantUserRole
from apps.multitenancy.models import TenantMembership
from apps.multitenancy.tests.factories import TenantFactory, TenantMembershipFactory
from apps.sso import constants
from apps.sso.models import SSOAuditLog, TenantDomain, TenantSSOConnection
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
from apps.sso.services import outbound
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


@pytest.fixture(autouse=True)
def public_idp_hosts():
    """The example IdP hosts used in these tests do not resolve in the sandbox. Treat them as public addresses."""
    with mock.patch.object(outbound, "_resolve_addresses", return_value=["93.184.216.34"]):
        yield


def _record_missing_past_grace(tenant_domain):
    """Simulate a record that has been missing for longer than the grace period, then re-check."""
    with mock.patch.object(dv, "lookup_txt_records", return_value=[]):
        dv.recheck_domain(tenant_domain)  # first failed check: owners are warned, grace period starts
        TenantDomain.objects.filter(pk=tenant_domain.pk).update(
            first_failed_at=timezone.now() - dv.LAPSE_AFTER_FAILURES - timedelta(days=1)
        )
        tenant_domain.refresh_from_db()
        return dv.recheck_domain(tenant_domain)


class TestPeriodicRecheck:
    def _verified(self, org, domain="client.pl"):
        claim = dv.add_domain(org, domain)
        with mock.patch.object(dv, "lookup_txt_records", return_value=[claim.verification_record_value]):
            return dv.verify_domain(claim)

    def test_challenge_is_published_on_the_subdomain(self, org):
        claim = dv.add_domain(org, "client.pl")

        assert claim.verification_record_name == "_klarvido-challenge.client.pl"

    def test_subdomain_record_verifies_a_claim(self, org):
        claim = dv.add_domain(org, "client.pl")
        subdomain_records = {"_klarvido-challenge.client.pl": [claim.verification_record_value]}

        with mock.patch.object(dv, "lookup_txt_records", side_effect=lambda name: subdomain_records.get(name, [])):
            dv.verify_domain(claim)

        claim.refresh_from_db()
        assert claim.status == VERIFIED

    def test_present_record_resets_the_failure_count(self, org):
        domain = self._verified(org)
        domain.consecutive_failures = 2
        domain.save()

        with mock.patch.object(dv, "lookup_txt_records", return_value=[domain.verification_record_value]):
            assert dv.recheck_domain(domain) == VERIFIED

        domain.refresh_from_db()
        assert domain.consecutive_failures == 0
        assert domain.last_checked_at is not None

    def _in_grace_period(self, org):
        domain = self._verified(org)
        with mock.patch.object(dv, "lookup_txt_records", return_value=[]):
            dv.recheck_domain(domain)  # warning shown, grace period starts
        domain.refresh_from_db()
        return domain

    def test_restoring_the_record_clears_the_warning_straight_away(self, org):
        domain = self._in_grace_period(org)
        assert domain.first_failed_at is not None

        with mock.patch.object(dv, "lookup_txt_records", return_value=[domain.verification_record_value]):
            dv.verify_domain(domain)

        domain.refresh_from_db()
        assert domain.status == VERIFIED
        assert domain.first_failed_at is None
        assert domain.consecutive_failures == 0

    def test_verify_during_grace_period_still_refuses_a_missing_record(self, org):
        domain = self._in_grace_period(org)
        first_failed_at = domain.first_failed_at

        with mock.patch.object(dv, "lookup_txt_records", return_value=[]):
            with pytest.raises(dv.DomainVerificationError) as exc:
                dv.verify_domain(domain)

        assert exc.value.code == dv.DNS_RECORD_NOT_FOUND_CODE
        domain.refresh_from_db()
        assert domain.first_failed_at == first_failed_at

    def test_lapsed_domain_is_verified_again_through_the_normal_path(self, org):
        domain = self._verified(org)
        _record_missing_past_grace(domain)
        domain.refresh_from_db()
        assert domain.status == constants.SSODomainStatus.LAPSED

        with mock.patch.object(dv, "lookup_txt_records", return_value=[domain.verification_record_value]):
            dv.verify_domain(domain)

        domain.refresh_from_db()
        assert domain.status == VERIFIED
        assert domain.first_failed_at is None

    def test_missing_record_lapses_only_after_the_grace_period(self, org):
        domain = self._verified(org)

        with mock.patch.object(dv, "lookup_txt_records", return_value=[]):
            assert dv.recheck_domain(domain) == VERIFIED  # first failure: warning, grace period starts
            assert dv.recheck_domain(domain) == VERIFIED  # still inside the grace period

        domain.refresh_from_db()
        assert domain.status == VERIFIED
        assert domain.first_failed_at is not None

        assert _record_missing_past_grace(domain) == constants.SSODomainStatus.LAPSED
        domain.refresh_from_db()
        assert domain.status == constants.SSODomainStatus.LAPSED

    def test_first_failed_check_warns_owners_and_does_not_lapse(self, org):
        from apps.notifications.models import Notification

        domain = self._verified(org)
        owner = UserFactory(email="warn-owner@sso-test.invalid")
        TenantMembershipFactory(user=owner, tenant=org, role=TenantUserRole.OWNER, is_accepted=True)

        with mock.patch.object(dv, "lookup_txt_records", return_value=[]):
            dv.recheck_domain(domain)

        assert Notification.objects.filter(user=owner, type="SSO_DOMAIN_RECORD_MISSING").count() == 1
        domain.refresh_from_db()
        assert domain.status == VERIFIED

    def test_record_found_again_resets_the_grace_period(self, org):
        domain = self._verified(org)
        with mock.patch.object(dv, "lookup_txt_records", return_value=[]):
            dv.recheck_domain(domain)
        with mock.patch.object(dv, "lookup_txt_records", return_value=[domain.verification_record_value]):
            dv.recheck_domain(domain)

        domain.refresh_from_db()
        assert domain.first_failed_at is None
        assert domain.consecutive_failures == 0

    def test_dns_error_changes_nothing(self, org):
        domain = self._verified(org)
        domain.consecutive_failures = 2
        domain.save()

        with mock.patch.object(dv, "lookup_txt_records", return_value=None):
            for _ in range(5):
                dv.recheck_domain(domain)

        domain.refresh_from_db()
        assert domain.status == VERIFIED
        assert domain.consecutive_failures == 2

    def test_lapse_deactivates_connections_and_keeps_memberships(self, org):
        domain = self._verified(org)
        connection = factories.TenantSSOConnectionFactory(
            tenant=org, allowed_domains=["client.pl"], status=constants.SSOConnectionStatus.ACTIVE
        )
        member = UserFactory(email="jan@client.pl")
        TenantMembershipFactory(user=member, tenant=org, is_accepted=True)

        _record_missing_past_grace(domain)

        connection.refresh_from_db()
        assert connection.status == constants.SSOConnectionStatus.INACTIVE
        assert TenantMembership.objects.filter(user=member, tenant=org).exists()
        assert SSOAuditLog.objects.filter(tenant=org, event_type=constants.SSOAuditEventType.DOMAIN_LAPSED).exists()

    def test_lapsed_domain_no_longer_routes_or_links_users(self, org):
        domain = self._verified(org)
        connection = factories.TenantSSOConnectionFactory(tenant=org, allowed_domains=["client.pl"])
        _record_missing_past_grace(domain)

        assert not is_email_domain_allowed(connection, "jan@client.pl")
        assert Query.resolve_sso_discover(None, None, "jan@client.pl")["sso_available"] is False

    def test_lapsed_domain_can_be_claimed_by_another_organization(self, org, other_org):
        domain = self._verified(org)
        _record_missing_past_grace(domain)

        claim = dv.add_domain(other_org, "client.pl")
        with mock.patch.object(dv, "lookup_txt_records", return_value=[claim.verification_record_value]):
            dv.verify_domain(claim)

        claim.refresh_from_db()
        assert claim.status == VERIFIED

    def test_lapsed_connection_cannot_be_reactivated_until_verified(self, org):
        domain = self._verified(org)
        connection = factories.TenantSSOConnectionFactory(tenant=org, allowed_domains=["client.pl"])
        _record_missing_past_grace(domain)

        with pytest.raises(dv.DomainVerificationError) as exc:
            dv.ensure_connection_domains_verified(connection)

        assert exc.value.code == dv.DOMAINS_NOT_VERIFIED_CODE

    def test_scheduled_task_rechecks_verified_domains(self, org):
        self._verified(org)
        from apps.sso.tasks import recheck_verified_domains

        with mock.patch.object(dv, "lookup_txt_records", return_value=[]) as lookup:
            with mock.patch("apps.sso.tasks.recheck_domain", wraps=dv.recheck_domain) as recheck:
                assert recheck_verified_domains() == 1

        assert recheck.call_count == 1
        assert lookup.called

    def test_scheduled_task_is_skipped_with_dev_bypass(self, org, settings):
        self._verified(org)
        from apps.sso.tasks import recheck_verified_domains

        settings.DEBUG = True
        settings.SSO_DOMAIN_VERIFICATION_SKIP_DNS = True
        with mock.patch.object(dv, "lookup_txt_records") as lookup:
            assert recheck_verified_domains() == 0

        lookup.assert_not_called()


class TestLapseNotifications:
    def _lapse(self, tenant_domain):
        _record_missing_past_grace(tenant_domain)

    def test_lapse_notifies_owners_and_the_connection_creator_once(self, org):
        from apps.notifications.models import Notification

        claim = dv.add_domain(org, "client.pl")
        with mock.patch.object(dv, "lookup_txt_records", return_value=[claim.verification_record_value]):
            dv.verify_domain(claim)

        owner = UserFactory(email="lapse-owner@sso-test.invalid")
        TenantMembershipFactory(user=owner, tenant=org, role=TenantUserRole.OWNER, is_accepted=True)
        creator = UserFactory(email="lapse-creator@sso-test.invalid")
        TenantMembershipFactory(user=creator, tenant=org, role=TenantUserRole.ADMIN, is_accepted=True)
        # The owner also created the connection: they must still get only one notification
        factories.TenantSSOConnectionFactory(
            tenant=org,
            allowed_domains=["client.pl"],
            status=constants.SSOConnectionStatus.ACTIVE,
            created_by=owner,
        )
        factories.TenantSSOConnectionFactory(
            tenant=org,
            allowed_domains=["client.pl"],
            status=constants.SSOConnectionStatus.ACTIVE,
            created_by=creator,
        )
        outsider = UserFactory(email="lapse-outsider@sso-test.invalid")

        self._lapse(claim)

        lapsed = Notification.objects.filter(type="SSO_DOMAIN_LAPSED")
        assert lapsed.filter(user=owner).count() == 1
        assert lapsed.filter(user=creator).count() == 1
        assert not lapsed.filter(user=outsider).exists()
        assert lapsed.first().data["domain"] == "client.pl"

    def test_lapse_emails_each_recipient_once(self, org):
        claim = dv.add_domain(org, "client.pl")
        with mock.patch.object(dv, "lookup_txt_records", return_value=[claim.verification_record_value]):
            dv.verify_domain(claim)
        owner = UserFactory(email="lapse-mail-owner@sso-test.invalid")
        TenantMembershipFactory(user=owner, tenant=org, role=TenantUserRole.OWNER, is_accepted=True)
        factories.TenantSSOConnectionFactory(
            tenant=org,
            allowed_domains=["client.pl"],
            status=constants.SSOConnectionStatus.ACTIVE,
            created_by=owner,
        )

        with mock.patch.object(dv, "SSODomainLapsedEmail") as email_class:
            self._lapse(claim)

        recipients = [call.args[0] for call in email_class.call_args_list]
        assert recipients.count(owner) == 1
        assert email_class.call_args.kwargs["data"]["grace_days"] == dv.LAPSE_AFTER_FAILURES.days

    def test_missing_record_warning_is_emailed_to_owners(self, org):
        claim = dv.add_domain(org, "client.pl")
        with mock.patch.object(dv, "lookup_txt_records", return_value=[claim.verification_record_value]):
            dv.verify_domain(claim)
        owner = UserFactory(email="warn-mail-owner@sso-test.invalid")
        TenantMembershipFactory(user=owner, tenant=org, role=TenantUserRole.OWNER, is_accepted=True)

        with mock.patch.object(dv, "SSODomainRecordMissingEmail") as email_class, mock.patch.object(
            dv, "lookup_txt_records", return_value=[]
        ):
            dv.recheck_domain(claim)

        recipients = [call.args[0] for call in email_class.call_args_list]
        assert recipients.count(owner) == 1
        assert email_class.call_args.kwargs["data"]["domain"] == "client.pl"

    def test_email_failure_does_not_stop_the_lapse(self, org):
        claim = dv.add_domain(org, "client.pl")
        with mock.patch.object(dv, "lookup_txt_records", return_value=[claim.verification_record_value]):
            dv.verify_domain(claim)

        with mock.patch.object(dv, "SSODomainLapsedEmail") as email_class:
            email_class.return_value.send.side_effect = RuntimeError("mail server down")
            self._lapse(claim)

        claim.refresh_from_db()
        assert claim.status == constants.SSODomainStatus.LAPSED

    def test_lapse_still_happens_when_notifications_fail(self, org):
        claim = dv.add_domain(org, "client.pl")
        with mock.patch.object(dv, "lookup_txt_records", return_value=[claim.verification_record_value]):
            dv.verify_domain(claim)
        TenantMembershipFactory(user=UserFactory(), tenant=org, role=TenantUserRole.OWNER, is_accepted=True)

        with mock.patch.object(dv.sender, "send_notification", side_effect=RuntimeError("boom")):
            self._lapse(claim)

        claim.refresh_from_db()
        assert claim.status == constants.SSODomainStatus.LAPSED


class TestSavingConnectionClaimsDomains:
    def _create_data(self, org, domains):
        return {
            "tenant_id": str(org.pk),
            "name": "Keycloak",
            "connection_type": constants.IdentityProviderType.SAML,
            "allowed_domains": domains,
            "saml_entity_id": "https://idp.example/entity",
            "saml_sso_url": "https://idp.example/sso",
        }

    def test_saving_a_new_domain_adds_it_as_a_pending_claim(self, org):
        serializer = TenantSSOConnectionSerializer(data=self._create_data(org, ["new-company.pl"]))
        serializer.is_valid(raise_exception=True)
        serializer.save()

        claim = TenantDomain.objects.get(tenant=org, domain="new-company.pl")
        assert claim.status == PENDING

    def test_public_domain_is_refused_before_saving(self, org):
        serializer = TenantSSOConnectionSerializer(data=self._create_data(org, ["gmail.com"]))

        assert not serializer.is_valid()
        assert serializer.errors["allowed_domains"][0] == dv.PUBLIC_DOMAIN_CODE
        assert not TenantSSOConnection.objects.filter(tenant=org).exists()

    def test_domain_verified_by_another_organization_is_refused(self, org, other_org):
        dv.add_domain(other_org, "taken.pl")
        TenantDomain.objects.filter(tenant=other_org, domain="taken.pl").update(status=VERIFIED)

        serializer = TenantSSOConnectionSerializer(data=self._create_data(org, ["taken.pl"]))

        assert not serializer.is_valid()
        assert serializer.errors["allowed_domains"][0] == dv.DOMAIN_TAKEN_CODE

    def test_updating_a_connection_claims_its_new_domains(self, org):
        connection = factories.TenantSSOConnectionFactory(tenant=org, allowed_domains=["client.pl"])
        serializer = UpdateTenantSSOConnectionSerializer(
            instance=connection, data={"allowed_domains": ["client.pl", "second.pl"]}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        assert TenantDomain.objects.get(tenant=org, domain="second.pl").status == PENDING

    def test_creating_a_connection_records_its_creator(self, org):
        user = UserFactory(email="setup-admin@sso-test.invalid")
        serializer = TenantSSOConnectionSerializer(
            data=self._create_data(org, ["creator-check.pl"]),
            context={"request": SimpleNamespace(user=user)},
        )
        serializer.is_valid(raise_exception=True)
        connection = serializer.save()

        assert connection.created_by == user
