"""
Security regression tests: an organization's identity provider (SSO or SCIM) must never be able to
take over, change, or lock an account that does not belong to that organization, and a SAML
signature must not be reusable around forged content (signature wrapping).
"""

import base64
import datetime
from unittest import mock

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree
from signxml import XMLSigner, methods

from apps.multitenancy.constants import TenantType, TenantUserRole
from apps.multitenancy.models import TenantMembership
from apps.multitenancy.tests.factories import TenantFactory, TenantMembershipFactory
from apps.sso import constants
from apps.sso.models import SCIMToken
from apps.sso.security import get_safe_error_code
from apps.sso.services.account_linking import AccountLinkingError
from apps.sso.services.provisioning import JITProvisioningService
from apps.sso.services.saml import SAMLService
from apps.sso.services.scim import SCIMError, SCIMService
from apps.users.tests.factories import UserFactory

from . import factories

pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return TenantFactory(type=TenantType.ORGANIZATION)


@pytest.fixture
def connection(org):
    return factories.TenantSSOConnectionFactory(
        tenant=org,
        status=constants.SSOConnectionStatus.ACTIVE,
        jit_provisioning_enabled=True,
        allowed_domains=["example.com"],
    )


@pytest.fixture
def scim_service(connection):
    token, _ = SCIMToken.create_for_tenant(tenant=connection.tenant, name="IdP", sso_connection=connection)
    return SCIMService(token)


def _member_of_another_org(email):
    user = UserFactory(email=email)
    TenantMembershipFactory(user=user, tenant=TenantFactory(type=TenantType.ORGANIZATION), is_accepted=True)
    return user


class TestJITProvisioningDoesNotTakeOverAccounts:
    def test_existing_account_outside_the_organization_is_rejected(self, connection):
        victim = _member_of_another_org("victim@example.com")

        with pytest.raises(AccountLinkingError):
            JITProvisioningService(connection).provision_or_update_user(idp_user_id="sub-1", email=victim.email)

        assert not TenantMembership.objects.filter(user=victim, tenant=connection.tenant).exists()

    def test_existing_member_of_the_organization_is_linked(self, connection):
        member = UserFactory(email="member@example.com")
        TenantMembershipFactory(user=member, tenant=connection.tenant, is_accepted=True, role=TenantUserRole.MEMBER)

        user, _, is_new = JITProvisioningService(connection).provision_or_update_user(
            idp_user_id="sub-2", email="Member@Example.com"
        )

        assert user == member
        assert is_new is False

    def test_pending_invitation_is_not_enough_to_link_an_account(self, connection):
        invited = _member_of_another_org("invited@example.com")
        TenantMembershipFactory(user=invited, tenant=connection.tenant, is_accepted=False)

        with pytest.raises(AccountLinkingError):
            JITProvisioningService(connection).provision_or_update_user(idp_user_id="sub-7", email=invited.email)

    def test_superuser_is_never_linked_even_as_member(self, connection):
        admin = UserFactory(email="root@example.com", is_superuser=True)
        TenantMembershipFactory(user=admin, tenant=connection.tenant, is_accepted=True)

        with pytest.raises(AccountLinkingError):
            JITProvisioningService(connection).provision_or_update_user(idp_user_id="sub-3", email=admin.email)

    def test_link_created_before_the_fix_cannot_sign_in_a_superuser(self, connection):
        admin = UserFactory(email="root2@example.com", is_superuser=True)
        factories.SSOUserLinkFactory(user=admin, sso_connection=connection, idp_user_id="old-link")

        with pytest.raises(AccountLinkingError):
            JITProvisioningService(connection).provision_or_update_user(idp_user_id="old-link", email=admin.email)

    def test_empty_domain_list_allows_no_one(self, connection):
        connection.allowed_domains = []
        connection.save()

        with pytest.raises(AccountLinkingError):
            JITProvisioningService(connection).provision_or_update_user(idp_user_id="sub-4", email="new@example.com")

    def test_domain_not_on_the_list_is_rejected(self, connection):
        with pytest.raises(AccountLinkingError):
            JITProvisioningService(connection).provision_or_update_user(idp_user_id="sub-5", email="new@gmail.com")

    def test_profile_of_account_used_by_another_organization_is_not_changed(self, connection):
        shared = _member_of_another_org("shared@example.com")
        shared.profile.first_name = "Original"
        shared.profile.save()
        TenantMembershipFactory(user=shared, tenant=connection.tenant, is_accepted=True)
        factories.SSOUserLinkFactory(user=shared, sso_connection=connection, idp_user_id="sub-6")

        JITProvisioningService(connection).provision_or_update_user(
            idp_user_id="sub-6", email=shared.email, first_name="Changed"
        )

        shared.profile.refresh_from_db()
        assert shared.profile.first_name == "Original"

    def test_rejection_is_shown_as_account_not_member(self):
        error = AccountLinkingError("Existing account is not a member of this organization.")

        assert get_safe_error_code(error) == "account_not_member"


class TestSCIMDoesNotTakeOverOrLockAccounts:
    def test_create_rejects_existing_account_outside_the_organization(self, scim_service):
        victim = _member_of_another_org("victim2@example.com")

        with pytest.raises(SCIMError) as exc:
            scim_service.create_user({"userName": victim.email})

        assert exc.value.status == 409
        assert not TenantMembership.objects.filter(user=victim, tenant=scim_service.tenant).exists()

    def test_create_rejects_domain_not_allowed(self, scim_service):
        with pytest.raises(SCIMError) as exc:
            scim_service.create_user({"userName": "someone@gmail.com"})

        assert exc.value.status == 400

    def test_create_rejects_superuser(self, scim_service):
        admin = UserFactory(email="root3@example.com", is_superuser=True)
        TenantMembershipFactory(user=admin, tenant=scim_service.tenant, is_accepted=True)

        with pytest.raises(SCIMError) as exc:
            scim_service.create_user({"userName": admin.email})

        assert exc.value.status == 409

    def test_deactivate_removes_membership_but_keeps_the_account_active(self, scim_service):
        created = scim_service.create_user({"userName": "worker@example.com", "externalId": "w-1"})
        user = UserFactory._meta.model.objects.get(email="worker@example.com")
        other_org = TenantFactory(type=TenantType.ORGANIZATION)
        TenantMembershipFactory(user=user, tenant=other_org, is_accepted=True)

        scim_service.patch_user(created["id"], [{"op": "replace", "path": "active", "value": False}])

        user.refresh_from_db()
        assert user.is_active is True
        assert not TenantMembership.objects.filter(user=user, tenant=scim_service.tenant).exists()
        assert TenantMembership.objects.filter(user=user, tenant=other_org).exists()

    def test_put_with_active_false_keeps_the_account_active(self, scim_service):
        created = scim_service.create_user({"userName": "worker2@example.com", "externalId": "w-2"})

        scim_service.update_user(created["id"], {"active": False})

        user = UserFactory._meta.model.objects.get(email="worker2@example.com")
        assert user.is_active is True
        assert scim_service.get_user(created["id"])["active"] is False

    def test_reactivation_restores_membership(self, scim_service):
        created = scim_service.create_user({"userName": "worker3@example.com", "externalId": "w-3"})
        scim_service.update_user(created["id"], {"active": False})

        result = scim_service.update_user(created["id"], {"active": True})

        assert result["active"] is True

    def test_name_of_account_used_by_another_organization_is_not_changed(self, scim_service):
        created = scim_service.create_user({"userName": "shared2@example.com", "externalId": "s-2"})
        user = UserFactory._meta.model.objects.get(email="shared2@example.com")
        TenantMembershipFactory(user=user, tenant=TenantFactory(type=TenantType.ORGANIZATION), is_accepted=True)
        user.profile.first_name = "Original"
        user.profile.save()

        scim_service.patch_user(created["id"], [{"op": "replace", "path": "name.givenName", "value": "Changed"}])

        user.profile.refresh_from_db()
        assert user.profile.first_name == "Original"


P = "urn:oasis:names:tc:SAML:2.0:protocol"
A = "urn:oasis:names:tc:SAML:2.0:assertion"
SUCCESS = '<samlp:Status><samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/></samlp:Status>'


ACS_URL = "https://sp.example.com/api/sso/saml/c1/acs"
SP_ENTITY_ID = "https://sp.example.com"


def _assertion(assertion_id, email):
    return (
        f'<saml:Assertion xmlns:saml="{A}" ID="{assertion_id}" Version="2.0" IssueInstant="2026-01-01T00:00:00Z">'
        "<saml:Issuer>idp</saml:Issuer>"
        "<saml:Subject><saml:NameID>" + email + "</saml:NameID>"
        f'<saml:SubjectConfirmation><saml:SubjectConfirmationData Recipient="{ACS_URL}"/></saml:SubjectConfirmation>'
        "</saml:Subject>"
        "<saml:Conditions><saml:AudienceRestriction>"
        f"<saml:Audience>{SP_ENTITY_ID}</saml:Audience>"
        "</saml:AudienceRestriction></saml:Conditions>"
        "</saml:Assertion>"
    )


@pytest.fixture(autouse=True)
def fixed_sp_identity():
    """The SP values every response in this module is addressed to."""
    with mock.patch.object(SAMLService, "get_acs_url", return_value=ACS_URL), mock.patch.object(
        SAMLService, "get_sp_entity_id", return_value=SP_ENTITY_ID
    ):
        yield


@pytest.fixture(scope="module")
def idp_keys():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "idp")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    return key_pem, cert.public_bytes(serialization.Encoding.PEM).decode()


def _sign(element, key_pem, cert_pem, reference_uri):
    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm="rsa-sha256",
        digest_algorithm="sha256",
        c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#",
    )
    return signer.sign(element, key=key_pem, cert=cert_pem, reference_uri=reference_uri)


def _saml_service(cert_pem):
    connection = mock.Mock(
        id="c1",
        saml_entity_id="idp",
        saml_certificate=cert_pem,
        saml_certificate_arn="",
        saml_want_response_signed=True,
        saml_want_assertions_signed=True,
        saml_attribute_mapping=None,
        tenant=None,
    )
    with mock.patch("apps.sso.services.saml.get_secrets_service"):
        return SAMLService(connection)


def _parse(service, xml_element):
    return service.parse_saml_response(base64.b64encode(etree.tostring(xml_element)).decode())


class TestSAMLSignatureWrapping:
    def test_signed_response_is_accepted(self, idp_keys):
        key_pem, cert_pem = idp_keys
        response = etree.fromstring(
            f'<samlp:Response xmlns:samlp="{P}" xmlns:saml="{A}" ID="R1" Destination="{ACS_URL}"><saml:Issuer>idp</saml:Issuer>{SUCCESS}{_assertion("A1", "user@example.com")}</samlp:Response>'
        )

        attrs = _parse(_saml_service(cert_pem), _sign(response, key_pem, cert_pem, "R1"))

        assert attrs["email"] == "user@example.com"

    def test_signed_assertion_is_accepted(self, idp_keys):
        key_pem, cert_pem = idp_keys
        signed_assertion = _sign(etree.fromstring(_assertion("A2", "user@example.com")), key_pem, cert_pem, "A2")
        response = etree.fromstring(
            f'<samlp:Response xmlns:samlp="{P}" xmlns:saml="{A}" ID="R2" Destination="{ACS_URL}"><saml:Issuer>idp</saml:Issuer>{SUCCESS}</samlp:Response>'
        )
        response.append(signed_assertion)

        attrs = _parse(_saml_service(cert_pem), response)

        assert attrs["email"] == "user@example.com"

    def test_signed_response_wrapped_in_forged_response_is_rejected(self, idp_keys):
        key_pem, cert_pem = idp_keys
        genuine = _sign(
            etree.fromstring(
                f'<samlp:Response xmlns:samlp="{P}" xmlns:saml="{A}" ID="R3" Destination="{ACS_URL}"><saml:Issuer>idp</saml:Issuer>{SUCCESS}{_assertion("A3", "attacker@example.com")}'
                "</samlp:Response>"
            ),
            key_pem,
            cert_pem,
            "R3",
        )
        forged = etree.fromstring(
            f'<samlp:Response xmlns:samlp="{P}" xmlns:saml="{A}" ID="EVIL" Destination="{ACS_URL}"><saml:Issuer>idp</saml:Issuer>{SUCCESS}{_assertion("F1", "victim@example.com")}'
            "<samlp:Extensions/></samlp:Response>"
        )
        forged.find(f"{{{P}}}Extensions").append(genuine)

        with pytest.raises(ValueError):
            _parse(_saml_service(cert_pem), forged)

    def test_forged_assertion_next_to_signed_assertion_is_rejected(self, idp_keys):
        key_pem, cert_pem = idp_keys
        signed_assertion = _sign(etree.fromstring(_assertion("A4", "attacker@example.com")), key_pem, cert_pem, "A4")
        response = etree.fromstring(
            f'<samlp:Response xmlns:samlp="{P}" xmlns:saml="{A}" ID="R4" Destination="{ACS_URL}"><saml:Issuer>idp</saml:Issuer>{SUCCESS}{_assertion("F2", "victim@example.com")}'
            "</samlp:Response>"
        )
        response.append(signed_assertion)

        with pytest.raises(ValueError):
            _parse(_saml_service(cert_pem), response)


class TestExistingLinksStillRequireMembership:
    def test_link_to_account_outside_the_organization_cannot_sign_in(self, connection):
        victim = _member_of_another_org("linked-victim@example.com")
        factories.SSOUserLinkFactory(user=victim, sso_connection=connection, idp_user_id="legacy")

        with pytest.raises(AccountLinkingError):
            JITProvisioningService(connection).provision_or_update_user(idp_user_id="legacy", email=victim.email)

        assert not TenantMembership.objects.filter(user=victim, tenant=connection.tenant).exists()


class TestSCIMCannotReviveForeignAccounts:
    def test_reactivating_a_link_to_an_account_used_elsewhere_is_rejected(self, scim_service, connection):
        victim = _member_of_another_org("revive@example.com")
        factories.SSOUserLinkFactory(
            user=victim, sso_connection=connection, idp_user_id="legacy-scim", provisioned_via_scim=True
        )

        with pytest.raises(SCIMError) as exc:
            scim_service.update_user("legacy-scim", {"active": True})

        assert exc.value.status == 409
        assert not TenantMembership.objects.filter(user=victim, tenant=connection.tenant).exists()
