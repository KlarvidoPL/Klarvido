"""
Tests for SSO GraphQL schema.

Note: These tests verify that GraphQL types and queries are properly registered.
More comprehensive tests will be added as mutations are implemented.
"""

import pytest
from graphql_relay import to_global_id
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.multitenancy.constants import TenantUserRole
from apps.multitenancy.models import TenantMembership
from apps.sso import models, constants

from . import factories


pytestmark = pytest.mark.django_db


class TestSSOGraphQLTypes:
    """Tests for SSO GraphQL types registration."""

    def test_sso_connection_type_exists(self, graphene_client):
        """Test that SSOConnectionType is registered in schema."""
        query = """
            query {
                __type(name: "SSOConnectionType") {
                    name
                    kind
                }
            }
        """

        response = graphene_client.query(query)

        assert response.get('errors') is None
        assert response['data']['__type'] is not None
        assert response['data']['__type']['name'] == 'SSOConnectionType'

    def test_scim_token_type_exists(self, graphene_client):
        """Test that SCIMTokenType is registered in schema."""
        query = """
            query {
                __type(name: "SCIMTokenType") {
                    name
                    kind
                }
            }
        """

        response = graphene_client.query(query)

        assert response.get('errors') is None
        assert response['data']['__type'] is not None
        assert response['data']['__type']['name'] == 'SCIMTokenType'

    def test_passkey_type_exists(self, graphene_client):
        """Test that PasskeyType is registered in schema."""
        query = """
            query {
                __type(name: "PasskeyType") {
                    name
                    kind
                }
            }
        """

        response = graphene_client.query(query)

        assert response.get('errors') is None
        assert response['data']['__type'] is not None
        assert response['data']['__type']['name'] == 'PasskeyType'

    def test_sso_session_type_exists(self, graphene_client):
        """Test that SSOSessionType is registered in schema."""
        query = """
            query {
                __type(name: "SSOSessionType") {
                    name
                    kind
                }
            }
        """

        response = graphene_client.query(query)

        assert response.get('errors') is None
        assert response['data']['__type'] is not None
        assert response['data']['__type']['name'] == 'SSOSessionType'

    def test_sso_audit_log_type_exists(self, graphene_client):
        """Test that SSOAuditLogType is registered in schema."""
        query = """
            query {
                __type(name: "SSOAuditLogType") {
                    name
                    kind
                }
            }
        """

        response = graphene_client.query(query)

        assert response.get('errors') is None
        assert response['data']['__type'] is not None
        assert response['data']['__type']['name'] == 'SSOAuditLogType'


class TestSSOMutationsRegistration:
    """Tests for SSO mutations registration."""

    def test_create_sso_connection_mutation_exists(self, graphene_client):
        """Test that createSsoConnection mutation is registered."""
        query = """
            query {
                __type(name: "ApiMutation") {
                    fields {
                        name
                    }
                }
            }
        """

        response = graphene_client.query(query)

        assert response.get('errors') is None
        field_names = [f['name'] for f in response['data']['__type']['fields']]
        assert 'createSsoConnection' in field_names

    def test_create_scim_token_mutation_exists(self, graphene_client):
        """Test that createScimToken mutation is registered."""
        query = """
            query {
                __type(name: "ApiMutation") {
                    fields {
                        name
                    }
                }
            }
        """

        response = graphene_client.query(query)

        assert response.get('errors') is None
        field_names = [f['name'] for f in response['data']['__type']['fields']]
        assert 'createScimToken' in field_names


class TestRevokeSessionMutation:
    """Tests for the revokeSession mutation - the "X" button in Active Sessions."""

    def test_revoke_session_blacklists_refresh_token(self, graphene_client, user):
        """The mutation must not just flag the session row inactive - it must
        blacklist the linked refresh token, or the device stays logged in."""
        refresh = RefreshToken.for_user(user)
        session = factories.SSOSessionFactory(user=user, refresh_token_jti=refresh['jti'])

        mutation = '''
            mutation RevokeSession($sessionId: String!) {
                revokeSession(sessionId: $sessionId) {
                    ok
                }
            }
        '''
        graphene_client.force_authenticate(user)

        response = graphene_client.mutate(mutation, variables={'sessionId': session.session_id})

        assert response.get('errors') is None
        assert response['data']['revokeSession']['ok'] is True

        session.refresh_from_db()
        assert session.is_active is False
        assert BlacklistedToken.objects.filter(token__jti=refresh['jti']).exists()

    def test_cannot_revoke_another_users_session(self, graphene_client, user, user_factory):
        """A user must not be able to revoke someone else's session by guessing its id."""
        other_user = user_factory()
        other_refresh = RefreshToken.for_user(other_user)
        other_session = factories.SSOSessionFactory(user=other_user, refresh_token_jti=other_refresh['jti'])

        mutation = '''
            mutation RevokeSession($sessionId: String!) {
                revokeSession(sessionId: $sessionId) {
                    ok
                }
            }
        '''
        graphene_client.force_authenticate(user)

        response = graphene_client.mutate(mutation, variables={'sessionId': other_session.session_id})

        assert response.get('errors') is not None

        other_session.refresh_from_db()
        assert other_session.is_active is True
        assert not BlacklistedToken.objects.filter(token__jti=other_refresh['jti']).exists()
