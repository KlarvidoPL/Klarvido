from types import SimpleNamespace

import pyotp
import pytest
from django.test import RequestFactory
from django.test import Client
from django.urls import reverse
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.core.files.base import ContentFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.demo.models import CrudDemoItem, DocumentDemoItem
from apps.multitenancy.constants import TenantType, TenantUserRole
from apps.multitenancy.models import ActionLog, ResourceCleanup, Tenant, TenantMembership
from apps.notifications.models import Notification
from apps.sso.services.passkey_management import password_grant
from apps.users.models import AccountDeletion, SecurityEmailOutbox, User
from apps.users.serializers import DeleteAccountSerializer
from apps.users.services.deletion import delete_account, deletion_blockers
from apps.users.services.security import deliver_email
from apps.multitenancy.cleanup import process_resource_cleanup

pytestmark = pytest.mark.django_db


def request_for(user):
    token = password_grant(user, {'action': 'account_delete', 'password': user._faker_password})
    request = RequestFactory().post('/api/graphql/', HTTP_X_PASSKEY_AUTHORIZATION=token)
    request.user = user
    return request


def test_last_owner_cannot_delete(user, tenant_factory, tenant_membership_factory):
    tenant = tenant_factory(creator=user, type=TenantType.ORGANIZATION)
    tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.OWNER)
    assert deletion_blockers(user) == [tenant]
    with pytest.raises(ValidationError) as error:
        delete_account(user.pk, request_for(user))
    assert error.value.get_codes() == {'confirmation': ['last_owner']}
    assert str(error.value) == 'GraphQlValidationError'
    assert User.objects.filter(pk=user.pk).exists()
    assert not AccountDeletion.objects.exists()


@pytest.mark.parametrize('accepted,active', [(False, True), (True, False)])
def test_pending_or_inactive_owner_does_not_unblock(
    user, tenant_factory, tenant_membership_factory, user_factory, accepted, active
):
    tenant = tenant_factory(creator=user, type=TenantType.ORGANIZATION)
    tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.OWNER)
    other = user_factory(is_active=active)
    tenant_membership_factory(user=other, tenant=tenant, role=TenantUserRole.OWNER, is_accepted=accepted)
    assert deletion_blockers(user) == [tenant]


def test_deletion_preserves_shared_data_and_severs_identity(
    user, user_factory, tenant_factory, tenant_membership_factory
):
    tenant = tenant_factory(creator=user, type=TenantType.ORGANIZATION)
    tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.OWNER)
    owner = user_factory()
    tenant_membership_factory(user=owner, tenant=tenant, role=TenantUserRole.OWNER)
    item = CrudDemoItem.objects.create(tenant=tenant, created_by=user, name='Shared')
    document = DocumentDemoItem.objects.create(tenant=tenant, created_by=user, file='shared.pdf')
    notice = Notification.objects.create(user=owner, issuer=user, type='TEST', data={})
    log = ActionLog.objects.create(
        tenant=tenant,
        actor_user=user,
        actor_email=user.email,
        action_type='create',
        entity_type='document',
        entity_id=str(document.pk),
    )
    original_id, original_email = str(user.pk), user.email
    name = str(user.profile)
    default_ids = list(Tenant.objects.filter(creator=user, type=TenantType.DEFAULT).values_list('pk', flat=True))
    request = request_for(user)
    delete_account(user.pk, request)
    assert not User.objects.filter(email=original_email).exists()
    assert not Tenant.objects.filter(pk__in=default_ids).exists()
    for obj in (tenant, item, document, notice, log):
        obj.refresh_from_db()
    assert tenant.creator_id is None
    assert item.created_by_id is None and document.created_by_id is None
    assert notice.issuer_id is None
    assert log.actor_user_id is None and log.actor_id_snapshot == original_id
    assert log.actor_name_snapshot == name and log.actor_email == original_email
    assert AccountDeletion.objects.filter(account_id=original_id).exists()
    assert SecurityEmailOutbox.objects.filter(kind='ACCOUNT_DELETED', user__isnull=True).exists()
    assert Notification.objects.filter(user=owner, type='MEMBER_ACCOUNT_DELETED').exists()
    assert request.reset_auth_cookie
    replacement = user_factory(email=original_email, profile__first_name='Different')
    assert str(replacement.pk) != original_id
    assert not TenantMembership.objects.filter(user=replacement, tenant=tenant).exists()
    log.refresh_from_db()
    assert log.actor_name_snapshot == name and log.actor_user_id is None


def test_cannot_delete_someone_else(user, user_factory):
    other = user_factory()
    with pytest.raises(PermissionDenied):
        delete_account(other.pk, request_for(user))


def test_proof_is_action_bound(user):
    token = password_grant(user, {'action': 'register', 'password': user._faker_password})
    request = RequestFactory().post('/', HTTP_X_PASSKEY_AUTHORIZATION=token)
    request.user = user
    with pytest.raises(PermissionDenied):
        delete_account(user.pk, request)


def test_changed_password_invalidates_proof(user):
    request = request_for(user)
    user.set_password('changed-secret')
    user.save(update_fields=['password'])
    with pytest.raises(PermissionDenied):
        delete_account(user.pk, request)


def test_otp_required_at_service_boundary(user):
    user.otp_base32 = pyotp.random_base32()
    user.otp_enabled = user.otp_verified = True
    user.save()
    with pytest.raises(ValidationError):
        delete_account(user.pk, request_for(user))


def test_otp_and_confirmation_delete_account(user):
    user.otp_base32 = pyotp.random_base32()
    user.otp_enabled = user.otp_verified = True
    user.save()
    request = request_for(user)
    serializer = DeleteAccountSerializer(
        data={'confirmation': user.email, 'otp_token': pyotp.TOTP(user.otp_base32).now()}, context={'request': request}
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.save() == {'ok': True}


def test_wrong_confirmation_preserves_account(user):
    serializer = DeleteAccountSerializer(data={'confirmation': 'wrong'}, context={'request': request_for(user)})
    assert not serializer.is_valid()
    assert User.objects.filter(pk=user.pk).exists()


def test_unassigned_personal_documents_are_cleaned(user):
    document = DocumentDemoItem.objects.create(created_by=user, file='documents/legacy.pdf')
    delete_account(user.pk, request_for(user))
    assert not DocumentDemoItem.objects.filter(pk=document.pk).exists()
    assert ResourceCleanup.objects.filter(resource_path='documents/legacy.pdf', resource_type='document_file').exists()


def test_old_pending_invitation_cannot_attach_to_new_registration(user, tenant_factory):
    tenant = tenant_factory(type=TenantType.ORGANIZATION)
    invitation = TenantMembership.objects.get_all().create(
        tenant=tenant, user=user, is_accepted=False, invitee_email_address=user.email
    )
    delete_account(user.pk, request_for(user))
    assert not TenantMembership.objects.get_all().filter(pk=invitation.pk).exists()


def test_last_administrator_is_protected(user_factory):
    user = user_factory(is_superuser=True)
    with pytest.raises(ValidationError):
        delete_account(user.pk, request_for(user), via_management=True)


def test_shared_personal_tenant_blocks_deletion(user, user_factory, tenant_membership_factory):
    private = Tenant.objects.get(creator=user, type=TenantType.DEFAULT)
    tenant_membership_factory(tenant=private, user=user_factory(), role=TenantUserRole.MEMBER)
    with pytest.raises(ValidationError):
        delete_account(user.pk, request_for(user))


def test_final_confirmation_delivers_without_account(mocker):
    delivery = SimpleNamespace(kind='ACCOUNT_DELETED', user_id=None, recipient='old@example.com', language='pl')
    send = mocker.patch('apps.users.services.security.deliver_email_message', return_value={'sent_emails_count': 1})
    assert deliver_email(delivery)
    send.assert_called_once_with('old@example.com', 'ACCOUNT_DELETED', {}, 'pl')


def test_graphql_deletion_revokes_access_and_clears_cookies(user, settings):
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
    grant = password_grant(user, {'action': 'account_delete', 'password': user._faker_password})
    response = client.post(
        '/api/graphql/',
        {
            'query': 'mutation($input: DeleteAccountMutationInput!) { deleteAccount(input: $input) { ok } }',
            'variables': {'input': {'confirmation': user.email}},
        },
        format='json',
        HTTP_X_PASSKEY_AUTHORIZATION=grant,
    )
    assert response.status_code == 200
    assert response.json().get('data', {}).get('deleteAccount', {}).get('ok'), response.json()
    assert response.cookies[settings.ACCESS_TOKEN_COOKIE]['max-age'] == 0
    later = client.post('/api/graphql/', {'query': '{ currentUser { id } }'}, format='json')
    assert later.status_code == 401


def test_cleanup_retries_and_keeps_neighbor_files(user, tmp_path, mocker):
    storage = FileSystemStorage(location=tmp_path)
    account_id = str(user.pk)
    storage.save(f'users/{account_id}/orphan.zip', ContentFile(b'personal'))
    storage.save(f'users/{account_id}other/keep.zip', ContentFile(b'neighbor'))
    mocker.patch('common.storages.get_user_exports_storage', return_value=storage)
    delete_account(user.pk, request_for(user))
    cleanup = ResourceCleanup.objects.get(resource_type='user_export_prefix', account_id=account_id)
    broken = mocker.patch('apps.multitenancy.cleanup.delete_user_exports', side_effect=OSError('offline'))
    assert not process_resource_cleanup(cleanup.pk)
    cleanup.refresh_from_db()
    assert cleanup.completed_at is None and cleanup.last_error == 'OSError'
    mocker.stop(broken)
    ResourceCleanup.objects.filter(pk=cleanup.pk).update(next_attempt_at=cleanup.created_at)
    assert process_resource_cleanup(cleanup.pk)
    assert not storage.exists(f'users/{account_id}/orphan.zip')
    assert storage.exists(f'users/{account_id}other/keep.zip')


def test_external_marker_reconciles_restored_account(user, user_factory, tmp_path, mocker):
    storage = FileSystemStorage(location=tmp_path)
    account_id = str(user.pk)
    mocker.patch('apps.multitenancy.cleanup.get_user_exports_storage', return_value=storage)
    delete_account(user.pk, request_for(user))
    assert process_resource_cleanup(
        ResourceCleanup.objects.get(resource_type='account_marker', account_id=account_id).pk
    )
    # Recreate an old database identity, as a full database restore would.
    restored = user_factory(id=account_id)
    administrator = user_factory(is_superuser=True)
    mocker.patch(
        'apps.users.management.commands.reconcile_deleted_accounts.get_user_exports_storage', return_value=storage
    )
    call_command('reconcile_deleted_accounts', administrator_id=str(administrator.pk))
    assert not User.objects.filter(pk=restored.pk).exists()
    replacement = user_factory()
    assert str(replacement.pk) != account_id


def test_admin_delete_requires_password_and_preserves_last_owner(user, user_factory, settings, mocker):
    settings.STORAGES = {
        **settings.STORAGES,
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
    administrator = user_factory(is_superuser=True)
    client = Client()
    client.force_login(administrator)
    url = reverse('admin:users_user_delete', args=[str(user.pk)])
    invalid = client.post(url, {'post': 'yes', 'password': 'wrong'})
    assert invalid.status_code == 200
    assert User.objects.filter(pk=user.pk).exists()
    valid = client.post(url, {'post': 'yes', 'password': administrator._faker_password})
    assert valid.status_code == 302
    assert not User.objects.filter(pk=user.pk).exists()


def test_admin_last_administrator_error_is_displayed(user_factory, settings):
    settings.STORAGES = {
        **settings.STORAGES,
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
    User.objects.filter(is_superuser=True).update(is_superuser=False)
    administrator = user_factory(is_superuser=True)
    client = Client()
    client.force_login(administrator)
    response = client.post(
        reverse('admin:users_user_delete', args=[str(administrator.pk)]),
        {'post': 'yes', 'password': administrator._faker_password},
    )
    assert response.status_code == 403
    assert User.objects.filter(pk=administrator.pk).exists()


@pytest.mark.parametrize('via_admin', [False, True])
def test_superuser_deletion_blocked_even_when_another_admin_exists(user_factory, via_admin):
    target = user_factory(is_superuser=True)
    user_factory(is_superuser=True)
    with pytest.raises(PermissionDenied):
        delete_account(target.pk, request_for(target), via_admin=via_admin)
    assert User.objects.filter(pk=target.pk).exists()


def test_superuser_serializer_rejects_direct_api_deletion(user_factory):
    target = user_factory(is_superuser=True)
    user_factory(is_superuser=True)
    serializer = DeleteAccountSerializer(data={'confirmation': target.email}, context={'request': request_for(target)})
    with pytest.raises(PermissionDenied):
        serializer.is_valid(raise_exception=True)


def test_superuser_management_command_uses_shared_cleanup(user_factory, mocker):
    target = user_factory(is_superuser=True)
    operator = user_factory(is_superuser=True)
    mocker.patch('builtins.input', return_value=target.email)
    mocker.patch('apps.users.management.commands.delete_superuser.getpass', return_value=operator._faker_password)
    call_command('delete_superuser', account_id=str(target.pk), administrator_id=str(operator.pk))
    assert not User.objects.filter(pk=target.pk).exists()
    assert AccountDeletion.objects.filter(account_id=str(target.pk)).exists()
