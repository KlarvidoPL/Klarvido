"""Email ownership must be proved before an invitation can grant organization access."""

import pytest
from django.conf import settings
from django.utils import timezone
from graphql_relay import to_global_id
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.multitenancy.constants import Notification as TenantNotification, TenantUserRole
from apps.multitenancy.notifications import send_tenant_invitation_notification
from apps.multitenancy.tokens import tenant_invitation_token
from apps.notifications.models import Notification
from apps.users.models import User
from apps.users.serializers import UserAccountConfirmationSerializer
from apps.users.tokens import account_activation_token

pytestmark = pytest.mark.django_db

TOKEN_QUERY = 'query($id: ID!) { tenant(id: $id) { membership { invitationToken } } }'
ACCEPT = '''mutation($input: AcceptTenantInvitationMutationInput!) {
    acceptTenantInvitation(input: $input) { ok }
}'''


@pytest.fixture(autouse=True)
def production_settings(settings):
    settings.DEBUG = False


def client_for(user):
    client = APIClient()
    client.cookies[settings.ACCESS_TOKEN_COOKIE] = str(RefreshToken.for_user(user).access_token)
    return client


def execute(client, query, variables=None):
    return client.post('/api/graphql/', {'query': query, 'variables': variables or {}}, format='json').json()


def pending_invitation(user, tenant_factory, tenant_membership_factory):
    return tenant_membership_factory(
        user=user, tenant=tenant_factory(), role=TenantUserRole.MEMBER, is_accepted=False, created_at=timezone.now()
    )


@pytest.mark.parametrize('confirmed', [False, True])
def test_invitation_token_requires_verified_email(
    confirmed, user_factory, tenant_factory, tenant_membership_factory, mocker
):
    user = user_factory(is_confirmed=confirmed)
    membership = pending_invitation(user, tenant_factory, tenant_membership_factory)
    make_token = mocker.patch(
        'apps.multitenancy.schema.tenant_invitation_token.make_token', wraps=tenant_invitation_token.make_token
    )
    result = execute(client_for(user), TOKEN_QUERY, {'id': to_global_id('TenantType', str(membership.tenant_id))})
    assert not result.get('errors'), result
    token = result['data']['tenant']['membership']['invitationToken']
    if confirmed:
        assert token
        assert tenant_invitation_token.check_token(user.email, token, membership)
        make_token.assert_called_once()
    else:
        assert token is None
        make_token.assert_not_called()

    make_token.reset_mock()
    node_result = execute(
        client_for(user),
        'query($id: ID!) { node(id: $id) { ... on TenantMembershipType { invitationToken } } }',
        {'id': to_global_id('TenantMembershipType', str(membership.pk))},
    )
    assert not node_result.get('errors'), node_result
    assert node_result['data']['node']['invitationToken'] == token
    if confirmed:
        make_token.assert_called_once()
    else:
        make_token.assert_not_called()


@pytest.mark.parametrize('confirmed', [False, True])
def test_acceptance_requires_verified_email_even_with_valid_token(
    confirmed, user_factory, tenant_factory, tenant_membership_factory, mocker
):
    user = user_factory(is_confirmed=confirmed)
    membership = pending_invitation(user, tenant_factory, tenant_membership_factory)
    notify = mocker.patch('apps.multitenancy.notifications.send_accepted_tenant_invitation_notification')
    result = execute(
        client_for(user),
        ACCEPT,
        {
            'input': {
                'id': to_global_id('TenantMembershipType', str(membership.pk)),
                'token': tenant_invitation_token.make_token(user.email, membership),
            }
        },
    )
    membership.refresh_from_db()
    assert membership.is_accepted is confirmed
    if confirmed:
        assert not result.get('errors'), result
        assert result['data']['acceptTenantInvitation']['ok']
        assert membership.invitation_accepted_at
        notify.assert_called_once()
        replay = execute(
            client_for(user),
            ACCEPT,
            {
                'input': {
                    'id': to_global_id('TenantMembershipType', str(membership.pk)),
                    'token': tenant_invitation_token.make_token(user.email, membership),
                }
            },
        )
        assert replay.get('errors'), replay
        notify.assert_called_once()
    else:
        assert result.get('errors'), result
        assert membership.invitation_accepted_at is None
        notify.assert_not_called()


@pytest.mark.parametrize('confirmed', [False, True])
def test_legacy_notification_tokens_are_never_exposed(confirmed, user_factory):
    user = user_factory(is_confirmed=confirmed)
    notification = Notification.objects.create(
        user=user,
        type=TenantNotification.TENANT_INVITATION_CREATED.value,
        data={'id': 'synthetic-invitation', 'token': 'synthetic-secret', 'tenant_name': 'Test'},
    )
    client = client_for(user)
    result = execute(client, '{ allNotifications { edges { node { data } } } }')
    assert not result.get('errors'), result
    assert result['data']['allNotifications']['edges'][0]['node']['data'] == {
        'id': 'synthetic-invitation',
        'tenant_name': 'Test',
    }
    result = execute(
        client,
        'query($id: ID!) { node(id: $id) { ... on NotificationType { data } } }',
        {'id': to_global_id('NotificationType', str(notification.pk))},
    )
    assert not result.get('errors'), result
    assert 'token' not in result['data']['node']['data']
    notification.refresh_from_db()
    assert notification.data['token'] == 'synthetic-secret'


def test_new_notifications_do_not_store_tokens(user, tenant_factory, tenant_membership_factory, mocker):
    membership = pending_invitation(user, tenant_factory, tenant_membership_factory)
    send = mocker.patch('apps.multitenancy.notifications.sender.send_notification')
    send_tenant_invitation_notification(membership, 'synthetic-invitation', 'synthetic-secret')
    assert 'token' not in send.call_args.kwargs['data']


def test_signup_with_invited_email_stays_blocked_until_email_confirmation(
    tenant_factory, tenant_membership_factory, mocker
):
    from types import SimpleNamespace

    membership = pending_invitation(None, tenant_factory, tenant_membership_factory)
    membership.invitee_email_address = 'invited-synthetic@example.com'
    membership.save(update_fields=['invitee_email_address'])
    user = User.objects.create_user(membership.invitee_email_address, 'synthetic-strong-password')
    membership.refresh_from_db()
    assert membership.user == user
    assert not user.is_confirmed
    client = client_for(user)
    variables = {'id': to_global_id('TenantType', str(membership.tenant_id))}
    assert execute(client, TOKEN_QUERY, variables)['data']['tenant']['membership']['invitationToken'] is None
    notify = mocker.patch('apps.multitenancy.notifications.send_accepted_tenant_invitation_notification')
    emailed_token = tenant_invitation_token.make_token(user.email, membership)
    acceptance = {'input': {'id': to_global_id('TenantMembershipType', str(membership.pk)), 'token': emailed_token}}
    assert execute(client, ACCEPT, acceptance).get('errors')
    notify.assert_not_called()
    confirmation = UserAccountConfirmationSerializer(
        data={'user': str(user.pk), 'token': account_activation_token.make_token(user)},
        context={'request': SimpleNamespace(user=user)},
    )
    assert confirmation.is_valid(), confirmation.errors
    confirmation.save()
    user.refresh_from_db()
    assert user.is_confirmed
    # The existing JWT can now use the verified state loaded from the database.
    assert execute(client, TOKEN_QUERY, variables)['data']['tenant']['membership']['invitationToken'] == emailed_token
    assert execute(client, ACCEPT, acceptance)['data']['acceptTenantInvitation']['ok']
    membership.refresh_from_db()
    assert membership.is_accepted


def test_unverified_user_keeps_own_workspace_and_can_create_organization(
    user_factory, tenant_factory, tenant_membership_factory
):
    user = user_factory(is_confirmed=False)
    pending_invitation(user, tenant_factory, tenant_membership_factory)
    client = client_for(user)
    result = execute(
        client,
        """{ currentUser { tenants {
        name billingEmail country nip actionLoggingEnabled onboardingRequired onboardingCompleted
        membership { invitationAccepted invitationToken }
    } } }""",
    )
    assert not result.get('errors'), result
    tenants = result['data']['currentUser']['tenants']
    assert any(tenant['membership']['invitationAccepted'] for tenant in tenants)
    invitation = next(tenant for tenant in tenants if not tenant['membership']['invitationAccepted'])
    assert invitation['membership']['invitationToken'] is None
    assert invitation['billingEmail'] is None
    assert invitation['country'] is None
    assert invitation['nip'] is None
    assert invitation['actionLoggingEnabled'] is None
    assert invitation['onboardingRequired'] is False
    assert invitation['onboardingCompleted'] is False
    result = execute(
        client,
        '''mutation($input: CreateTenantMutationInput!) {
        createTenant(input: $input) { tenant { id name membership { invitationAccepted } } }
    }''',
        {
            'input': {
                'name': 'Synthetic own organization',
                'billingEmail': user.email,
                'nip': '9721382373',
                'companyName': 'Synthetic Company',
                'regon': '123456785',
                'address': 'Synthetic address',
                'vatStatus': 'ACTIVE',
            }
        },
    )
    assert not result.get('errors'), result
    assert result['data']['createTenant']['tenant']['membership']['invitationAccepted']
    user.refresh_from_db()
    assert not user.is_confirmed
