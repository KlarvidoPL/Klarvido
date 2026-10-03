import channels_graphql_ws
from graphql import GraphQLError, OperationDefinitionNode, OperationType, parse

from config.schema import schema as graphql_schema


class DefaultGraphqlWsConsumer(channels_graphql_ws.GraphqlWsConsumer):
    """Channels WebSocket consumer which provides GraphQL API."""

    schema = graphql_schema

    async def on_operation(self, op_id, payload):
        """
        Only subscriptions may run over the WebSocket.

        The resolver permission layer (common/graphql/acl/wrappers.py::check_permissions) skips every check for
        WebSocket requests, since they carry no DRF request to evaluate. Queries and mutations must therefore go over
        HTTP, where authentication and every permission class apply - the web app only ever sends subscriptions here.
        """
        try:
            document = parse(payload.get("query") or "")
        except GraphQLError:
            raise GraphQLError("Invalid GraphQL document")

        operations = [
            definition for definition in document.definitions if isinstance(definition, OperationDefinitionNode)
        ]
        if not operations or any(operation.operation != OperationType.SUBSCRIPTION for operation in operations):
            raise GraphQLError("Only subscriptions are allowed over WebSocket; send queries and mutations over HTTP")
