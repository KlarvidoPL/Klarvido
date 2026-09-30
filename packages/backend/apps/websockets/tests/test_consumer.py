import pytest
from asgiref.sync import async_to_sync
from channels_graphql_ws.client import GraphqlWsResponseError
from channels_graphql_ws.testing import GraphqlWsClient, GraphqlWsTransport
from django.conf import settings
from graphql_relay import to_global_id
from rest_framework_simplejwt.tokens import RefreshToken

from config.asgi import application

# transaction=True: the WebSocket consumer runs in its own thread, outside the test transaction. serialized_rollback puts
# back the rows seeded by migrations (permissions, groups) that the post-test flush would otherwise wipe for later tests
pytestmark = pytest.mark.django_db(transaction=True, serialized_rollback=True)

SUBSCRIPTION = "subscription { notificationCreated { notification { id } } }"


def run_over_websocket(query, user=None, subscribe=False):
    """Connect to /api/graphql/ over the WebSocket and run one operation; returns the response (or raises)."""

    headers = []
    if user:
        # Minted before entering the async client: it touches the database
        access_token = RefreshToken.for_user(user).access_token
        headers = [(b"cookie", f"{settings.ACCESS_TOKEN_COOKIE}={access_token}".encode())]

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
