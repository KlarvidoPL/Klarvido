import graphene

from . import acl as graphql_acl
from .acl.wrappers import PermissionNodeField, wraps_object_type


def graphql_query(queries):
    class Query(*queries, graphene.ObjectType):
        node = PermissionNodeField(graphene.relay.Node)

    return wraps_object_type(Query, graphql_acl.get_default_permission_classes(), defaults=True)


def graphql_mutation(mutations):
    class ApiMutation(*mutations, graphene.ObjectType):
        pass

    return wraps_object_type(ApiMutation, graphql_acl.get_default_permission_classes(), defaults=True)


def graphql_subscription(subscriptions):
    class ApiSubscription(*subscriptions, graphene.ObjectType):
        pass

    return ApiSubscription
