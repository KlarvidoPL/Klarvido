from datetime import timedelta

import pytest
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from channels_graphql_ws.client import GraphqlWsResponseError
from channels_graphql_ws.testing import GraphqlWsClient, GraphqlWsTransport
from django.conf import settings
from graphql_relay import to_global_id
from rest_framework_simplejwt.tokens import RefreshToken

from apps.notifications.schema import NotificationCreatedSubscription
from config.asgi import application

# The consumer runs in its own thread: use transaction=True. Serialized rollback restores migration seed rows
# (permissions, groups) after each test flush.
pytestmark = pytest.mark.django_db(transaction=True, serialized_rollback=True)

TRUSTED_ORIGIN = 'https://klarvido.example'


@pytest.fixture(autouse=True)
def trusted_origins(mocker):
    # ASGI middleware captures configuration at startup, as it does on the VPS.
    mocker.patch.object(
        application.application_mapping['websocket'],
        'allowed_origins',
        [TRUSTED_ORIGIN, 'http://localhost:3000', 'http://127.0.0.1:3000'],
    )


SUBSCRIPTION = "subscription { notificationCreated { notification { id } } }"


def run_over_websocket(query, user=None, subscribe=False, cookie_token=None):
    """Connect to /api/graphql/ over the WebSocket and run one operation; returns the response (or raises)."""

    headers = [(b"origin", TRUSTED_ORIGIN.encode())]
    if user or cookie_token:
        # Minted before entering the async client: it touches the database
        access_token = cookie_token or RefreshToken.for_user(user).access_token
        headers.append((b"cookie", f"{settings.ACCESS_TOKEN_COOKIE}={access_token}".encode()))

    async def run():
        client = GraphqlWsClient(
            GraphqlWsTransport(application=application, path="api/graphql/", communicator_kwds={"headers": headers})
        )
        await client.connect_and_init()
        try:
            if subscribe:
                await client.subscribe(SUBSCRIPTION, wait_confirmation=False)
                await client.assert_no_messages("An allowed subscription must not be answered with an error")
                return None
            msg_id = await client.start(query)
            return await client.receive(assert_id=msg_id)
        finally:
            await client.finalize()

    return async_to_sync(run)()


def assert_refused(query, user=None):
    with pytest.raises(GraphqlWsResponseError) as error:
        run_over_websocket(query, user=user)
    assert "Only subscriptions are allowed over WebSocket" in str(error.value)


class TestOnlySubscriptionsOverWebsocket:
    """The resolver permission layer is skipped for WebSocket requests, so nothing but subscriptions may run there."""

    def test_query_is_refused(self, tenant_factory):
        tenant = tenant_factory(name="Secret Org")
        assert_refused(
            'query { node(id: "%s") { ... on TenantType { name } } }' % to_global_id("TenantType", tenant.id)
        )

    def test_query_is_refused_for_a_signed_in_user_too(self, user):
        assert_refused("query { currentUser { email } }", user=user)

    def test_mutation_is_refused(self, user):
        assert_refused('mutation { markReadAllNotifications(input: {}) { ok } }', user=user)

    def test_document_mixing_a_subscription_with_a_query_is_refused(self, user):
        assert_refused(SUBSCRIPTION + " query Q { currentUser { email } }", user=user)

    def test_subscription_is_allowed(self, user):
        run_over_websocket(SUBSCRIPTION, user=user, subscribe=True)


@pytest.mark.parametrize(
    'origin',
    [
        None,
        'null',
        'https://attacker.example',
        'https://klarvido.example.attacker.example',
        'http://klarvido.example',
        'https://klarvido.example:444',
        'https://sub.klarvido.example',
        'http://localhost:3001',
    ],
)
def test_untrusted_origin_is_rejected_before_cookie_authentication(origin, user, mocker):
    authenticate = mocker.patch('apps.users.authentication.JSONWebTokenCookieMiddleware.authenticate')
    access_token = RefreshToken.for_user(user).access_token
    headers = [(b'cookie', f'{settings.ACCESS_TOKEN_COOKIE}={access_token}'.encode())]
    if origin is not None:
        headers.append((b'origin', origin.encode()))

    async def connect():
        communicator = WebsocketCommunicator(application, '/api/graphql/', headers=headers)
        connected, _ = await communicator.connect()
        assert not connected
        await communicator.disconnect()

    async_to_sync(connect)()
    authenticate.assert_not_called()


@pytest.mark.parametrize(
    'origin',
    [
        TRUSTED_ORIGIN,
        'https://klarvido.example:443',
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    ],
)
def test_trusted_origin_preserves_cookie_authentication(origin, user, mocker):
    authenticate = mocker.spy(application.application_mapping['websocket'].application, 'authenticate')
    access_token = RefreshToken.for_user(user).access_token
    headers = [(b'origin', origin.encode()), (b'cookie', f'{settings.ACCESS_TOKEN_COOKIE}={access_token}'.encode())]

    async def connect():
        client = GraphqlWsClient(
            GraphqlWsTransport(application=application, path='api/graphql/', communicator_kwds={'headers': headers})
        )
        await client.connect_and_init()
        try:
            await client.subscribe(SUBSCRIPTION, wait_confirmation=False)
            await client.assert_no_messages('Trusted frontend must still receive subscriptions')
        finally:
            await client.finalize()

    async_to_sync(connect)()
    assert authenticate.spy_return[0].pk == user.pk


@pytest.mark.parametrize('credential', ['anonymous', 'expired', 'inactive'])
def test_trusted_origin_does_not_bypass_subscription_authentication(credential, user_factory):
    cookie_token = None
    if credential != 'anonymous':
        user = user_factory(is_active=credential != 'inactive')
        cookie_token = RefreshToken.for_user(user).access_token
        if credential == 'expired':
            cookie_token.set_exp(lifetime=timedelta(seconds=-1))
        cookie_token = str(cookie_token)
    with pytest.raises(GraphqlWsResponseError, match='Authentication required'):
        run_over_websocket(SUBSCRIPTION, cookie_token=cookie_token)


@pytest.mark.parametrize('own', [True, False])
def test_notification_subscription_preserves_ownership(own, user, user_factory, notification_factory):
    notification = notification_factory(user=user if own else user_factory())
    response = async_to_sync(NotificationCreatedSubscription.get_response)(id=str(notification.pk), user_id=user.pk)
    if own:
        assert response.notification.pk == notification.pk
    else:
        assert response is None
