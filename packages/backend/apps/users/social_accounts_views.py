from django.db import DatabaseError
from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from social_django.models import UserSocialAuth

from common.csrf import enforce_api_csrf
from apps.sso.views import PasskeyAPIView
from apps.sso.passkey_security import validate_request, client_ip
from apps.sso.serializers import PasskeyTextField, VerifyPasskeySerializer
from rest_framework import serializers
from apps.sso.models import UserPasskey, SSOAuditLog
from apps.sso.constants import SSOAuditEventType
from apps.sso.exceptions import PasskeyReauthenticationError
from apps.users.utils import reset_auth_cookie
from apps.users.services.social_linking import LINK_COOKIE
from apps.users.services.social_unlink import can_unlink, unlink_options, unlink_account


class SocialAccountTargetSerializer(serializers.Serializer):
    associationId = PasskeyTextField(max_length=20)


class SocialAccountPasswordSerializer(SocialAccountTargetSerializer):
    password = PasskeyTextField(max_length=4096, trim_whitespace=False)
    otpToken = PasskeyTextField(max_length=16, required=False, allow_blank=True, trim_whitespace=False)


class SocialAccountPasskeySerializer(VerifyPasskeySerializer, SocialAccountTargetSerializer):
    pass


class SocialAccountsView(PasskeyAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        response = Response(
            {
                'accounts': [
                    {'id': str(row.pk), 'provider': row.provider, 'canUnlink': can_unlink(request.user, row)}
                    for row in UserSocialAuth.objects.filter(user=request.user).order_by('pk')
                ],
                'hasPasskey': UserPasskey.objects.filter(user=request.user, is_active=True).exists(),
                'hasPassword': request.user.has_usable_password(),
                'otpEnabled': request.user.otp_enabled,
            }
        )
        response['Cache-Control'] = 'no-store'
        return response


class SocialUnlinkOptionsView(PasskeyAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        enforce_api_csrf(request)
        data = validate_request(SocialAccountTargetSerializer, request)
        response = Response(unlink_options(request.user, data['associationId']))
        response['Cache-Control'] = 'no-store'
        return response


class SocialUnlinkView(PasskeyAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        enforce_api_csrf(request)
        serializer = (
            SocialAccountPasskeySerializer if request.data.get('challenge') else SocialAccountPasswordSerializer
        )
        data = validate_request(serializer, request)
        try:
            unlink_account(request.user, data, client_ip(request))
        except DatabaseError:
            response = Response(
                {'error': 'Unable to disconnect. Please try again.', 'code': 'service_unavailable'}, status=503
            )
            response['Cache-Control'] = 'no-store'
            return response
        except (ValueError, PermissionDenied, ValidationError) as exc:
            SSOAuditLog.log_event(
                SSOAuditEventType.SSO_LOGIN_FAILED,
                user=request.user,
                success=False,
                description='Social unlink verification failed',
                metadata={'action': 'account_unlink_failed'},
            )
            response = Response(
                {
                    'error': 'Verification failed',
                    'code': exc.reason if isinstance(exc, PasskeyReauthenticationError) else 'verification_failed',
                },
                status=403,
            )
            response['Cache-Control'] = 'no-store'
            return response
        response = Response({'success': True})
        response['Cache-Control'] = 'no-store'
        reset_auth_cookie(response)
        response.delete_cookie(LINK_COOKIE, samesite=settings.COOKIE_SAMESITE)
        response.delete_cookie(settings.OTP_AUTH_TOKEN_COOKIE, samesite=settings.COOKIE_SAMESITE)
        return response
