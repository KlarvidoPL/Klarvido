"""Read-only inventory: legacy social rows do not record how ownership was proved."""

from social_django.models import UserSocialAuth

from apps.sso.models import SSOAuditLog, UserPasskey


def historical_link_candidates():
    proven = {
        (str(value['metadata'].get('association_id')), str(value['user_id']), value['metadata'].get('provider'))
        for value in SSOAuditLog.objects.filter(success=True, metadata__action='account_linked').values(
            'metadata', 'user_id'
        )
        if value['metadata'].get('association_id') is not None
    }
    for association in UserSocialAuth.objects.select_related('user').order_by('pk').iterator():
        if (str(association.pk), str(association.user_id), association.provider) in proven:
            continue
        account = association.user
        yield {
            'association_id': str(association.pk),
            'user_id': str(account.pk),
            'provider': association.provider,
            'confirmed': account.is_confirmed,
            'active': account.is_active,
            'has_password': account.has_usable_password(),
            'has_otp': account.otp_enabled,
            'active_passkeys': UserPasskey.objects.filter(user=account, is_active=True).count(),
            'memberships': account.tenant_memberships.count(),
            'status': 'ownership_proof_not_recorded',
        }
