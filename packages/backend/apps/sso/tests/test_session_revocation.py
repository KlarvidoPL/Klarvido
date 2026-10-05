"""
Deactivating or lapsing an SSO connection must end the sessions it created, not only stop new sign-ins.

Sessions from other sign-in methods, and from other connections, must be left alone.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.sso import constants
from apps.sso.serializers import ActivateSSOConnectionSerializer
from apps.sso.tests import factories

pytestmark = pytest.mark.django_db


def _sso_session(connection, jti=""):
    link = factories.SSOUserLinkFactory(sso_connection=connection)
    return factories.SSOSessionFactory(user=link.user, sso_link=link, refresh_token_jti=jti)


class TestConnectionDeactivationRevokesSessions:
    def test_deactivating_revokes_sessions_created_through_that_connection(self, tenant):
        connection = factories.TenantSSOConnectionFactory(tenant=tenant, status=constants.SSOConnectionStatus.ACTIVE)
        session = _sso_session(connection)

        connection.deactivate()

        session.refresh_from_db()
        assert session.is_active is False
        assert session.revoked_reason == "SSO connection deactivated"
        assert session.revoked_at is not None

    def test_deactivating_blacklists_the_refresh_token_of_the_session(self, tenant):
        connection = factories.TenantSSOConnectionFactory(tenant=tenant, status=constants.SSOConnectionStatus.ACTIVE)
        jti = "deactivated-jti"
        session = _sso_session(connection, jti=jti)
        token_body = "outstanding-token-body"
        OutstandingToken.objects.create(
            user=session.user,
            jti=jti,
            token=token_body,
            expires_at=timezone.now() + timedelta(days=1),
        )

        connection.deactivate()

        assert BlacklistedToken.objects.filter(token__jti=jti).exists()

    def test_sessions_from_other_connections_and_password_logins_are_kept(self, tenant):
        connection = factories.TenantSSOConnectionFactory(tenant=tenant, status=constants.SSOConnectionStatus.ACTIVE)
        other_connection = factories.TenantSSOConnectionFactory(
            tenant=tenant, status=constants.SSOConnectionStatus.ACTIVE
        )
        other_session = _sso_session(other_connection)
        password_session = factories.SSOSessionFactory()

        connection.deactivate()

        other_session.refresh_from_db()
        password_session.refresh_from_db()
        assert other_session.is_active is True
        assert password_session.is_active is True

    def test_saving_the_inactive_status_directly_also_revokes(self, tenant):
        """A lapsed domain deactivates its connections with a plain save, so that path must revoke too."""
        connection = factories.TenantSSOConnectionFactory(tenant=tenant, status=constants.SSOConnectionStatus.ACTIVE)
        session = _sso_session(connection)

        connection.status = constants.SSOConnectionStatus.INACTIVE
        connection.save(update_fields=["status", "updated_at"])

        session.refresh_from_db()
        assert session.is_active is False


class TestActivatingAnotherConnectionRevokesThePrevious:
    def test_activation_revokes_sessions_of_the_previously_active_connection(self, tenant):
        previous = factories.TenantSSOConnectionFactory(tenant=tenant, status=constants.SSOConnectionStatus.ACTIVE)
        previous_session = _sso_session(previous)
        replacement = factories.TenantSSOConnectionFactory(tenant=tenant, status=constants.SSOConnectionStatus.DRAFT)

        serializer = ActivateSSOConnectionSerializer(data={"id": str(replacement.pk), "tenant_id": str(tenant.pk)})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        previous.refresh_from_db()
        previous_session.refresh_from_db()
        replacement.refresh_from_db()
        assert previous.status == constants.SSOConnectionStatus.INACTIVE
        assert previous_session.is_active is False
        assert replacement.status == constants.SSOConnectionStatus.ACTIVE
