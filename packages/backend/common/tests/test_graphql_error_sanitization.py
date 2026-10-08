import asyncio

import graphene
import pytest
from django.conf import settings
from django.db import OperationalError
from graphql import GraphQLError
from promise import Promise
from rest_framework.exceptions import AuthenticationFailed, ValidationError

from apps.users.exceptions import OTPAttemptLimitExceeded, OTPVerificationFailure
from apps.websockets.consumers import DefaultGraphqlWsConsumer
from common.graphql.exceptions import GraphQlValidationError
from common.graphql.security import GENERIC_ERROR, SanitizeErrorsMiddleware
from common.graphql.views import DRFAuthenticatedGraphQLView

pytestmark = pytest.mark.django_db
SECRET_DETAIL = 'database password=private-secret; tenant=customer-a; SQL SELECT private_data'


class Query(graphene.ObjectType):
    broken = graphene.String()
    otp = graphene.String()
    validation = graphene.String()
    permission = graphene.String()
    healthy = graphene.String(number=graphene.Int())

    def resolve_broken(root, info):
        raise OperationalError(SECRET_DETAIL)

    def resolve_otp(root, info):
        raise OTPVerificationFailure('Verification token is invalid')

    def resolve_validation(root, info):
        raise GraphQlValidationError({'email': ['Enter a valid email address.']})

    def resolve_permission(root, info):
        raise GraphQLError('permission_denied')

    def resolve_healthy(root, info, **kwargs):
        return 'ok'


@pytest.fixture
def production(settings):
    settings.DEBUG = False


@pytest.mark.usefixtures('production')
@pytest.mark.parametrize(
    'original', [OperationalError(SECRET_DETAIL), RuntimeError(SECRET_DETAIL), ValueError(SECRET_DETAIL)]
)
@pytest.mark.parametrize(
    'format_error', [DRFAuthenticatedGraphQLView.format_error, DefaultGraphqlWsConsumer._format_error]
)
def test_response_formatters_hide_unexpected_details(original, format_error, mocker):
    report = mocker.patch('common.graphql.security.capture_exception')
    error = GraphQLError(
        'Invalid ' + SECRET_DETAIL, original_error=original, path=['broken'], extensions={'sql': SECRET_DETAIL}
    )
    result = format_error(error)
    assert result['message'] == GENERIC_ERROR
    assert result['extensions'] == {'code': 'internal_server_error'}
    assert result['path'] == ['broken']
    assert SECRET_DETAIL not in str(result)
    report.assert_called_once_with(original)


@pytest.mark.usefixtures('production')
def test_exception_name_does_not_make_internal_error_safe():
    fake_validation_error = type('ValidationError', (Exception,), {})(SECRET_DETAIL)
    assert (
        DRFAuthenticatedGraphQLView.format_error(GraphQLError(SECRET_DETAIL, original_error=fake_validation_error))[
            'message'
        ]
        == GENERIC_ERROR
    )


@pytest.mark.usefixtures('production')
@pytest.mark.parametrize(
    'original',
    [
        ValidationError({'email': ['Invalid email']}),
        GraphQlValidationError({'email': ['Invalid email']}),
        AuthenticationFailed('Incorrect credentials'),
        OTPVerificationFailure('Verification token is invalid'),
        OTPAttemptLimitExceeded('Too many incorrect codes. Try again in 15 minutes.'),
    ],
)
def test_expected_client_errors_remain_readable(original):
    result = DRFAuthenticatedGraphQLView.format_error(GraphQLError(str(original), original_error=original))
    assert result['message'] == str(original)
    if isinstance(original, ValidationError):
        assert result['extensions']['email'][0]['code'] == 'invalid'


def test_debug_keeps_diagnostics(settings):
    settings.DEBUG = True
    result = DRFAuthenticatedGraphQLView.format_error(
        GraphQLError(SECRET_DETAIL, original_error=RuntimeError(SECRET_DETAIL))
    )
    assert result['message'] == SECRET_DETAIL


@pytest.mark.usefixtures('production')
def test_http_execution_hides_errors_and_preserves_partial_data(api_client, settings, mocker):
    settings.GRAPHENE = {**settings.GRAPHENE, 'SCHEMA': graphene.Schema(query=Query)}
    mocker.patch('graphene_django.views.graphene_settings.SCHEMA', graphene.Schema(query=Query))
    response = api_client.post(
        '/api/graphql/', {'query': '{ broken healthy otp validation permission }'}, format='json'
    )
    result = response.json()
    assert response.status_code == 200, result
    assert SECRET_DETAIL not in str(result)
    assert result['data']['healthy'] == 'ok'
    by_path = {error['path'][0]: error for error in result['errors']}
    assert by_path['broken']['message'] == GENERIC_ERROR
    assert by_path['otp']['message'] == 'Verification token is invalid'
    assert by_path['permission']['message'] == 'permission_denied'
    assert by_path['validation']['message'] == 'GraphQlValidationError'
    assert by_path['validation']['extensions']['email'][0]['message'] == 'Enter a valid email address.'


@pytest.mark.usefixtures('production')
@pytest.mark.parametrize('query', ['{', '{ notAField }', 'query A { healthy } query B { healthy }'])
def test_request_errors_do_not_crash(api_client, settings, query, mocker):
    settings.GRAPHENE = {**settings.GRAPHENE, 'SCHEMA': graphene.Schema(query=Query)}
    mocker.patch('graphene_django.views.graphene_settings.SCHEMA', graphene.Schema(query=Query))
    response = api_client.post('/api/graphql/', {'query': query}, format='json')
    assert response.status_code == 400
    assert response.json()['errors']


@pytest.mark.usefixtures('production')
@pytest.mark.parametrize('mode', ['sync', 'async', 'promise'])
def test_resolver_middleware_handles_all_execution_styles(mode):
    middleware = SanitizeErrorsMiddleware()

    def fail(*args):
        raise RuntimeError(SECRET_DETAIL)

    async def async_fail(*args):
        fail()

    def promise_fail(*args):
        return Promise.reject(RuntimeError(SECRET_DETAIL))

    with pytest.raises(GraphQLError, match=GENERIC_ERROR):
        if mode == 'async':
            asyncio.run(middleware.resolve(async_fail, None, None))
        elif mode == 'promise':
            middleware.resolve(promise_fail, None, None).get()
        else:
            middleware.resolve(fail, None, None)


@pytest.mark.usefixtures('production')
def test_variable_validation_stays_readable(api_client, mocker):
    mocker.patch('graphene_django.views.graphene_settings.SCHEMA', graphene.Schema(query=Query))
    response = api_client.post(
        '/api/graphql/',
        {
            'query': 'query($number: Int) { healthy(number: $number) }',
            'variables': {'number': 'wrong-type'},
        },
        format='json',
    )
    assert 'Int cannot represent' in response.json()['errors'][0]['message']


@pytest.mark.usefixtures('production')
@pytest.mark.parametrize('valid_password,otp', [(True, False), (False, False), (True, True)])
def test_production_login_and_otp_challenge_remain_compatible(api_client, user_factory, valid_password, otp, faker):
    password = faker.password()
    account = user_factory(password=password, otp_enabled=otp, otp_verified=otp)
    response = api_client.post(
        '/api/graphql/',
        {
            'query': (
                'mutation($input: ObtainTokenMutationInput!) {'
                ' tokenAuth(input: $input) { authenticated otpRequired access refresh otpAuthToken } }'
            ),
            'variables': {
                'input': {
                    'email': account.email,
                    'password': password if valid_password else 'incorrect',
                }
            },
        },
        format='json',
    )
    result = response.json()
    if valid_password:
        assert not result.get('errors'), result
        payload = result['data']['tokenAuth']
        assert payload['otpRequired'] == otp
        assert payload['authenticated'] != otp
        assert payload['access'] is None
        assert payload['refresh'] is None
        assert payload['otpAuthToken'] is None
        cookie = settings.OTP_AUTH_TOKEN_COOKIE if otp else settings.ACCESS_TOKEN_COOKIE
        assert response.cookies[cookie].value
        assert response.cookies[cookie]['httponly']
    else:
        assert result['errors'][0]['message'] != GENERIC_ERROR
        assert 'no_active_account' in str(result['errors'])
