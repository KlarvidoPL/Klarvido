"""Fresh-auth gating for 2FA enable/replace/disable (E02), and that each login
code is only ever accepted once (E07). See apps.users.serializers (GenerateOTP/
VerifyOTP/DisableOTP) and apps.sso.services.passkey_management (otp_only_grant).
"""

from unittest.mock import patch

import pyotp
import pytest
from graphql_relay import to_global_id
from rest_framework.test import APIClient

from apps.sso.constants import SSOAuditEventType
from apps.sso.models import PasskeyManagementGrant, SSOAuditLog
from apps.users.models import SecurityEmailOutbox

pytestmark = pytest.mark.django_db

GENERATE_OTP = 'mutation($input: GenerateOTPMutationInput!) { generateOtp(input: $input) { base32 otpauthUrl } }'
VERIFY_OTP = 'mutation($input: VerifyOTPMutationInput!) { verifyOtp(input: $input) { otpVerified } }'
DISABLE_OTP = 'mutation($input: DisableOTPMutationInput!) { disableOtp(input: $input) { ok } }'
LOGIN = 'mutation($input: ObtainTokenMutationInput!) { ' 'tokenAuth(input: $input) { authenticated otpRequired } }'
VALIDATE_OTP = 'mutation($input: ValidateOTPMutationInput!) { validateOtp(input: $input) { authenticated } }'

PASSWORD = 'Fresh-auth-password-42!'
VERIFY_URL = '/api/sso/passkeys/reauthenticate/verify'


def grant_token(client, action, **data):
    response = client.post(VERIFY_URL, {'action': action, **data}, format='json')
    assert response.status_code == 200, response.data
    return response.data['authorization']


def with_grant(client, token):
    client.credentials(HTTP_X_PASSKEY_AUTHORIZATION=token)
    return client


class TestGrantIsActionBound:
    def test_otp_setup_grant_cannot_disable(self, user_factory):
        user = user_factory(otp_enabled=True, otp_verified=True, otp_base32=pyotp.random_base32())
        user.set_password(PASSWORD)
        user.save(update_fields=['password'])
        client = APIClient()
        client.force_authenticate(user)
        token = grant_token(client, 'otp_setup', password=PASSWORD, otpToken=pyotp.TOTP(user.otp_base32).now())

        response = with_grant(client, token).post(
            '/api/graphql/', {'query': DISABLE_OTP, 'variables': {'input': {}}}, format='json'
        )

        assert response.json()['errors']
        assert user_factory._meta.model.objects.get(pk=user.pk).otp_enabled

    def test_otp_disable_grant_cannot_setup(self, user_factory):
        user = user_factory(otp_enabled=True, otp_verified=True, otp_base32=pyotp.random_base32())
        user.set_password(PASSWORD)
        user.save(update_fields=['password'])
        client = APIClient()
        client.force_authenticate(user)
        token = grant_token(client, 'otp_disable', password=PASSWORD, otpToken=pyotp.TOTP(user.otp_base32).now())

        response = with_grant(client, token).post(
            '/api/graphql/', {'query': GENERATE_OTP, 'variables': {'input': {}}}, format='json'
        )

        assert response.json()['errors']

    def test_passkey_delete_grant_cannot_be_used_for_otp(self, user_factory, user_passkey_factory):
        user = user_factory()
        user.set_password(PASSWORD)
        user.save(update_fields=['password'])
        passkey = user_passkey_factory(user=user)
        client = APIClient()
        client.force_authenticate(user)
        token = grant_token(client, 'delete', password=PASSWORD, passkeyId=to_global_id('PasskeyType', passkey.pk))

        response = with_grant(client, token).post(
            '/api/graphql/', {'query': GENERATE_OTP, 'variables': {'input': {}}}, format='json'
        )

        assert response.json()['errors']


class TestOtpOnlyGrantForPasswordlessPasskeylessAccount:
    def test_can_disable_with_current_code_alone(self, user_factory):
        user = user_factory(otp_enabled=True, otp_verified=True, otp_base32=pyotp.random_base32())
        user.set_unusable_password()
        user.save(update_fields=['password'])
        client = APIClient()
        client.force_authenticate(user)

        token = grant_token(client, 'otp_disable', otpToken=pyotp.TOTP(user.otp_base32).now())
        response = with_grant(client, token).post(
            '/api/graphql/', {'query': DISABLE_OTP, 'variables': {'input': {}}}, format='json'
        )

        assert response.json()['data']['disableOtp']['ok'] is True
        assert not user_factory._meta.model.objects.get(pk=user.pk).otp_enabled

    def test_wrong_code_is_rejected(self, user_factory):
        user = user_factory(otp_enabled=True, otp_verified=True, otp_base32=pyotp.random_base32())
        user.set_unusable_password()
        user.save(update_fields=['password'])
        client = APIClient()
        client.force_authenticate(user)
        response = client.post(VERIFY_URL, {'action': 'otp_disable', 'otpToken': 'wrong'}, format='json')

        assert response.status_code == 403
        assert not PasskeyManagementGrant.objects.exists()

    def test_otp_only_grant_refused_when_password_is_available(self, user_factory):
        # An account that *can* prove freshness more strongly must not fall back
        # to the weaker, code-only path.
        user = user_factory(otp_enabled=True, otp_verified=True, otp_base32=pyotp.random_base32())
        user.set_password(PASSWORD)
        user.save(update_fields=['password'])
        client = APIClient()
        client.force_authenticate(user)

        response = client.post(
            VERIFY_URL, {'action': 'otp_disable', 'otpToken': pyotp.TOTP(user.otp_base32).now()}, format='json'
        )

        assert response.status_code == 403
        assert not PasskeyManagementGrant.objects.exists()

    def test_otp_only_grant_refused_for_register_action(self, user_factory):
        user = user_factory(otp_enabled=True, otp_verified=True, otp_base32=pyotp.random_base32())
        user.set_unusable_password()
        user.save(update_fields=['password'])
        client = APIClient()
        client.force_authenticate(user)

        response = client.post(
            VERIFY_URL, {'action': 'register', 'otpToken': pyotp.TOTP(user.otp_base32).now()}, format='json'
        )

        assert response.status_code == 403


class TestAuditAndNotifications:
    def test_enabling_is_audited_and_notified(self, user_factory, django_capture_on_commit_callbacks):
        user = user_factory()
        user.set_unusable_password()
        user.save(update_fields=['password'])
        client = APIClient()
        client.force_authenticate(user)
        gen = client.post('/api/graphql/', {'query': GENERATE_OTP, 'variables': {'input': {}}}, format='json')
        base32 = gen.json()['data']['generateOtp']['base32']

        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(
                '/api/graphql/',
                {'query': VERIFY_OTP, 'variables': {'input': {'otpToken': pyotp.TOTP(base32).now()}}},
                format='json',
            )

        assert response.json()['data']['verifyOtp']['otpVerified'] is True
        assert SSOAuditLog.objects.filter(event_type=SSOAuditEventType.OTP_ENABLED, user=user).exists()
        assert SecurityEmailOutbox.objects.filter(user=user, kind='OTP_ENABLED').count() == 1

    def test_disabling_is_audited_and_notified(self, user_factory, django_capture_on_commit_callbacks):
        user = user_factory(otp_enabled=True, otp_verified=True, otp_base32=pyotp.random_base32())
        user.set_password(PASSWORD)
        user.save(update_fields=['password'])
        client = APIClient()
        client.force_authenticate(user)
        token = grant_token(client, 'otp_disable', password=PASSWORD, otpToken=pyotp.TOTP(user.otp_base32).now())

        with django_capture_on_commit_callbacks(execute=True):
            response = with_grant(client, token).post(
                '/api/graphql/', {'query': DISABLE_OTP, 'variables': {'input': {}}}, format='json'
            )

        assert response.json()['data']['disableOtp']['ok'] is True
        assert SSOAuditLog.objects.filter(event_type=SSOAuditEventType.OTP_DISABLED, user=user).exists()
        assert SecurityEmailOutbox.objects.filter(user=user, kind='OTP_DISABLED').count() == 1


class TestLoginCodeIsSingleUse:
    def test_same_code_cannot_be_submitted_twice(self, user_factory):
        secret = pyotp.random_base32()
        user = user_factory(otp_enabled=True, otp_verified=True, otp_base32=secret)
        user.set_password(PASSWORD)
        user.save(update_fields=['password'])
        client = APIClient()
        login = client.post(
            '/api/graphql/',
            {'query': LOGIN, 'variables': {'input': {'email': user.email, 'password': PASSWORD}}},
            format='json',
        )
        assert login.json()['data']['tokenAuth']['otpRequired']
        code = pyotp.TOTP(secret).now()

        first = client.post(
            '/api/graphql/', {'query': VALIDATE_OTP, 'variables': {'input': {'otpToken': code}}}, format='json'
        )
        assert first.json()['data']['validateOtp']['authenticated'] is True

        # A second login, same credentials, same still-valid code.
        login2 = client.post(
            '/api/graphql/',
            {'query': LOGIN, 'variables': {'input': {'email': user.email, 'password': PASSWORD}}},
            format='json',
        )
        assert login2.json()['data']['tokenAuth']['otpRequired']
        second = client.post(
            '/api/graphql/', {'query': VALIDATE_OTP, 'variables': {'input': {'otpToken': code}}}, format='json'
        )

        assert second.json()['errors']
