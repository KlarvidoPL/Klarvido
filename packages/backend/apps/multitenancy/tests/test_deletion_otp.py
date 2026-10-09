from types import SimpleNamespace

import pyotp
import pytest
from django.contrib.admin.models import LogEntry, DELETION
from django.urls import reverse

from ..models import Tenant, ResourceCleanup, OrganizationDeletionDelivery
from ..services.deletion import delete_organization
from common.graphql.exceptions import GraphQlValidationError
from .test_tenant_deletion import delete_tenant
from .test_admin_deletion import deletion_admin  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def otp_owner(user_factory, tenant_factory, tenant_membership_factory, mocker):
    actor = user_factory(otp_enabled=True, otp_verified=True, otp_base32=pyotp.random_base32())
    tenant = tenant_factory(type='organization')
    tenant_membership_factory(tenant=tenant, user=actor, role='OWNER')
    mocker.patch('apps.multitenancy.schema.close_old_connections')
    mocker.patch('apps.multitenancy.cleanup.current_app.send_task')
    mocker.patch('apps.multitenancy.services.deletion.subscriptions.get_schedule', return_value=None)
    return actor, tenant


@pytest.mark.parametrize('token', [None, 'invalid'])
def test_missing_or_invalid_otp_cannot_delete_or_schedule_work(otp_owner, graphene_client, token):
    actor, tenant = otp_owner
    result = delete_tenant(graphene_client, actor, tenant, otp_token=token)
    assert result.get('errors')
    assert Tenant.objects.filter(pk=tenant.pk).exists()
    assert not ResourceCleanup.objects.exists()
    assert not OrganizationDeletionDelivery.objects.exists()
    assert not LogEntry.objects.filter(object_id=str(tenant.pk), action_flag=DELETION).exists()


def test_valid_otp_allows_deletion(otp_owner, graphene_client):
    actor, tenant = otp_owner
    tenant_id = str(tenant.pk)
    result = delete_tenant(graphene_client, actor, tenant, pyotp.TOTP(actor.otp_base32).now())
    assert not result.get('errors'), result
    assert not Tenant.objects.filter(pk=tenant_id).exists()
    assert ResourceCleanup.objects.filter(organization_id=tenant_id).exists()


def test_failed_otp_counters_persist_and_lock_out_deletion(otp_owner):
    actor, tenant = otp_owner
    for _ in range(5):
        with pytest.raises(GraphQlValidationError):
            delete_organization(
                tenant.pk, SimpleNamespace(user=actor, META={'REMOTE_ADDR': '127.0.0.1'}), otp_token='invalid'
            )
    actor.refresh_from_db()
    assert actor.otp_failed_attempts == 5
    assert actor.otp_locked_until is not None
    with pytest.raises(GraphQlValidationError):
        delete_organization(
            tenant.pk,
            SimpleNamespace(user=actor, META={'REMOTE_ADDR': '127.0.0.1'}),
            otp_token=pyotp.TOTP(actor.otp_base32).now(),
        )
    assert Tenant.objects.filter(pk=tenant.pk).exists()


def test_used_otp_cannot_delete_another_organization(otp_owner, tenant_factory, tenant_membership_factory):
    actor, first = otp_owner
    second = tenant_factory(type='organization')
    tenant_membership_factory(tenant=second, user=actor, role='OWNER')
    token = pyotp.TOTP(actor.otp_base32).now()
    delete_organization(first.pk, SimpleNamespace(user=actor, META={'REMOTE_ADDR': '127.0.0.1'}), otp_token=token)
    with pytest.raises(GraphQlValidationError):
        delete_organization(second.pk, SimpleNamespace(user=actor, META={'REMOTE_ADDR': '127.0.0.1'}), otp_token=token)
    assert Tenant.objects.filter(pk=second.pk).exists()


@pytest.mark.parametrize('bulk', [False, True])
def test_admin_requires_otp_and_preserves_failed_attempts(bulk, deletion_admin, tenant_factory):
    client, actor, queue, email = deletion_admin
    actor.otp_enabled = actor.otp_verified = True
    actor.otp_base32 = pyotp.random_base32()
    actor.save(update_fields=['otp_enabled', 'otp_verified', 'otp_base32'])
    tenant = tenant_factory(type='organization')
    tenant_id = str(tenant.pk)
    if bulk:
        url = reverse('admin:multitenancy_tenant_changelist')
        fields = {'action': 'delete_selected', '_selected_action': [tenant_id], 'post': 'yes'}
    else:
        url = reverse('admin:multitenancy_tenant_delete', args=[tenant_id])
        fields = {'post': 'yes'}
    response = client.post(url, {**fields, 'otp_token': 'invalid'})
    assert response.status_code == 200
    assert b'name="otp_token"' in response.content
    actor.refresh_from_db()
    assert actor.otp_failed_attempts == 1
    assert Tenant.objects.filter(pk=tenant_id).exists()
    queue.assert_not_called()
    email.assert_not_called()
    response = client.post(url, {**fields, 'otp_token': pyotp.TOTP(actor.otp_base32).now()})
    assert response.status_code == 302
    assert not Tenant.objects.filter(pk=tenant_id).exists()
