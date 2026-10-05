import asyncio
import csv
import io
import json
import hashlib
import zipfile
import uuid
from types import SimpleNamespace
import base64
import os
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, AsyncMock

from cryptography.hazmat.primitives import padding as symmetric_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from apps.integrations.ai_assistant.subscription import AiChatSubscription, SendAiMessageMutation
import httpx
import pytest
from django.conf import settings
from django.utils import timezone
from graphql_relay import to_global_id
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.backup.registry import BackupModelRegistry
from apps.backup.service import BackupService
from apps.backup.restore import RestoreService
from apps.invoices import services, tasks
from apps.invoices.ai_context import invoice_context
from rest_framework.exceptions import PermissionDenied
from apps.invoices.ksef import KsefSession, KsefSyncError
from apps.invoices.models import (
    Invoice,
    InvoiceCategory,
    InvoiceLine,
    InvoiceSyncRun,
    InvoiceSyncState,
    InvoiceImportError,
)
from apps.invoices.parser import InvoiceParseError, parse_invoice
from apps.invoices.query import invoice_queryset, summary
from apps.ksef import crypto
from apps.ksef.models import KsefCredential
from apps.multitenancy.constants import TenantType, TenantUserRole
from apps.multitenancy.models import (
    OrganizationRole,
    Permission,
    TenantMembershipRole,
    invalidate_user_permissions_cache,
)

pytestmark = pytest.mark.django_db


def xml(variant=3, currency='PLN', kind='VAT'):
    return f'''<Faktura xmlns="http://crd.gov.pl/test"><Naglowek><KodFormularza>FA</KodFormularza><WariantFormularza>{variant}</WariantFormularza></Naglowek>
<Podmiot1><DaneIdentyfikacyjne><NIP>5252344078</NIP><Nazwa>Seller</Nazwa></DaneIdentyfikacyjne></Podmiot1><Podmiot2><DaneIdentyfikacyjne><NIP>1234567890</NIP><Nazwa>Buyer</Nazwa></DaneIdentyfikacyjne></Podmiot2>
<Fa><KodWaluty>{currency}</KodWaluty><P_1>2026-01-01</P_1><P_2>FV/1</P_2><P_13_1>100.00</P_13_1><P_14_1>23.00</P_14_1><P_14_1W>99</P_14_1W><P_15>123.00</P_15><RodzajFaktury>{kind}</RodzajFaktury>
<DaneFaKorygowanej><NrKSeFFaKorygowanej>original-not-imported</NrKSeFFaKorygowanej></DaneFaKorygowanej><FaWiersz><P_7>Service</P_7><P_8B>2</P_8B><P_9A>50</P_9A><P_11>100</P_11><P_12>23</P_12></FaWiersz></Fa></Faktura>'''


@pytest.fixture
def state(tenant_factory, settings):
    settings.KSEF_ENVIRONMENT = 'test'
    settings.KSEF_ENCRYPTION_KEYS = base64.b64encode(os.urandom(32)).decode()
    tenant = tenant_factory(nip='5252344078', country='PL', type=TenantType.ORGANIZATION)
    KsefCredential.objects.create(
        tenant=tenant,
        encrypted_token=crypto.encrypt_token(tenant.pk, 'secret'),
        token_hint='secret'[-4:],
        status='VALID',
    )
    return InvoiceSyncState.objects.create(
        tenant=tenant, context_nip=tenant.nip, environment='test', start_date=timezone.now() - timedelta(days=365)
    )


def meta(number='test-ksef-number'):
    return {'ksefNumber': number, 'permanentStorageDate': timezone.now().isoformat()}


@pytest.mark.parametrize('variant', [2, 3])
@pytest.mark.parametrize('kind', ['VAT', 'KOR'])
def test_parser_currency_positions_and_corrections(variant, kind):
    result = parse_invoice(xml(variant, 'EUR', kind))
    assert result['net'] == Decimal('100')
    assert result['vat'] == Decimal('23')  # P_14_*W is PLN, not invoice currency.
    assert result['currency'] == 'EUR'
    assert result['corrected_ksef_numbers'] == ['original-not-imported']
    assert result['lines'][0]['quantity'] == 2


@pytest.mark.parametrize('document', ['broken', '<!DOCTYPE x><x/>', xml(1), xml().replace('100.00', 'NaN')])
def test_parser_rejects_unsafe_or_unsupported(document):
    with pytest.raises(InvoiceParseError):
        parse_invoice(document)


def test_reimport_preserves_category_and_does_not_duplicate(state):
    assert tasks.import_document(state, meta(), xml(2), 'Subject1')
    invoice = Invoice.objects.get()
    invoice.category = InvoiceCategory.objects.create(tenant=state.tenant, name='User choice')
    invoice.save()
    assert not tasks.import_document(state, meta(), xml(3), 'Subject1')
    invoice.refresh_from_db()
    assert invoice.category.name == 'User choice'
    assert Invoice.objects.count() == InvoiceLine.objects.count() == 1


def test_tenant_nip_environment_isolation_and_currency_summary(state, tenant_factory):
    tasks.import_document(state, meta('one'), xml(currency='EUR'), 'Subject1')
    tasks.import_document(state, meta('two'), xml(), 'Subject2')
    assert len(summary(invoice_queryset(state.tenant))) == 2
    assert not invoice_queryset(tenant_factory(nip=state.context_nip)).exists()
    state.tenant.nip = 'changed'
    assert not invoice_queryset(state.tenant).exists()
    state.tenant.nip = state.context_nip
    assert invoice_queryset(state.tenant, direction='PURCHASE', category='uncategorized').count() == 1


@patch('apps.invoices.tasks.sync_invoices.apply_async')
def test_sync_completion_truncation_retry_and_checkpoint(enqueue, state):
    run = InvoiceSyncRun.objects.create(tenant=state.tenant, state=state)
    package = {'isTruncated': True, 'lastPermanentStorageDate': state.start_date.isoformat()}
    with patch('apps.invoices.tasks.KsefSession') as factory:
        session = factory.return_value.__enter__.return_value
        session.start_export.return_value = {'reference': 'export', 'subject': 'Subject1'}
        tasks.sync_invoices(run.pk)
        session.export_status.return_value = package
        session.read_package.return_value = [(meta(), xml())]
        tasks.sync_invoices(run.pk)
        state.refresh_from_db()
        assert state.checkpoints['Subject1'] == state.start_date.isoformat()
        run.refresh_from_db()
        assert run.completed_subjects == []
        # Repeat same boundary document in the next, complete package.
        tasks.sync_invoices(run.pk)
        session.export_status.return_value = {
            'isTruncated': False,
            'permanentStorageHwmDate': run.created_at.isoformat(),
        }
        tasks.sync_invoices(run.pk)
        run.refresh_from_db()
        assert run.completed_subjects == ['Subject1']
        tasks.sync_invoices(run.pk)
        session.read_package.return_value = [(meta('purchase'), xml(2))]
        tasks.sync_invoices(run.pk)
        tasks.sync_invoices(run.pk)
    run.refresh_from_db()
    assert run.status == 'COMPLETED'
    assert run.imported_count == 2
    assert Invoice.objects.count() == 2
    state.refresh_from_db()
    assert state.last_success_at


@pytest.mark.parametrize(
    'code, delay, expected',
    [
        ('NO_PERMISSIONS', 0, 'PARTIAL'),
        ('INVALID_TOKEN', 0, 'PARTIAL'),
        ('RATE_LIMITED', 120, 'QUEUED'),
        ('SERVICE_UNAVAILABLE', 60, 'QUEUED'),
    ],
)
@patch('apps.invoices.tasks.sync_invoices.apply_async')
def test_sync_errors(enqueue, state, code, delay, expected):
    run = InvoiceSyncRun.objects.create(tenant=state.tenant, state=state, completed_subjects=['Subject1'])
    with patch('apps.invoices.tasks.KsefSession') as session:
        session.return_value.__enter__.side_effect = KsefSyncError(code, delay)
        tasks.sync_invoices(run.pk)
    run.refresh_from_db()
    assert run.status == expected
    assert run.error_code == code
    if delay:
        assert enqueue.call_args.kwargs['countdown'] >= delay


@patch('apps.invoices.tasks.sync_invoices.apply_async')
def test_invalid_document_keeps_source_without_advancing_checkpoint(enqueue, state):
    run = InvoiceSyncRun.objects.create(tenant=state.tenant, state=state, pending_export={'reference': 'export'})
    with patch('apps.invoices.tasks.KsefSession') as factory:
        session = factory.return_value.__enter__.return_value
        session.export_status.return_value = {
            'isTruncated': False,
            'permanentStorageHwmDate': timezone.now().isoformat(),
        }
        session.read_package.return_value = [(meta(), 'invalid')]
        tasks.sync_invoices(run.pk)
    state.refresh_from_db()
    assert state.checkpoints == {}
    assert InvoiceImportError.objects.get().raw_xml == 'invalid'


@patch('apps.invoices.tasks.sync_invoices.apply_async')
def test_manual_and_automatic_sync_share_one_active_run(enqueue, state, user):
    first = services.start_sync(state.tenant, user)
    assert services.start_sync(state.tenant, user).pk == first.pk
    tasks.schedule_invoice_syncs()
    assert InvoiceSyncRun.objects.count() == 1


def test_refresh_and_retry_after():
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith('/auth/token/refresh'):
            return httpx.Response(200, json={'accessToken': {'token': 'new'}})
        return httpx.Response(401 if len(calls) == 1 else 429, headers={'Retry-After': '180'})

    with httpx.Client(base_url='https://ksef.invalid', transport=httpx.MockTransport(handler)) as http:
        session = KsefSession('nip', 'secret', http)
        session.access, session.refresh = 'expired', 'refresh'
        with pytest.raises(KsefSyncError) as exc:
            session.request('GET', '/invoices/exports/ref')
        assert exc.value.code == 'RATE_LIMITED' and exc.value.retry_after == 180
        assert calls[-1].headers['Authorization'] == 'Bearer new'


def test_backup_includes_sources_and_excludes_technical_state():
    BackupModelRegistry.auto_discover_all()
    assert all(BackupModelRegistry.is_registered(model) for model in [Invoice, InvoiceCategory, InvoiceLine])
    assert all(
        not BackupModelRegistry.is_registered(model) for model in [InvoiceSyncState, InvoiceSyncRun, InvoiceImportError]
    )


@pytest.mark.parametrize('codes, allowed', [([], False), (['invoices.view'], True)])
def test_real_graphql_permissions_and_foreign_invoice(state, user_factory, tenant_membership_factory, codes, allowed):
    user = user_factory()
    membership = tenant_membership_factory(tenant=state.tenant, user=user, role=TenantUserRole.MEMBER)
    TenantMembershipRole.objects.filter(membership=membership).delete()
    role = OrganizationRole.objects.create(tenant=state.tenant, name='Invoice test')
    role.permissions.add(*Permission.objects.filter(code__in=codes))
    TenantMembershipRole.objects.create(membership=membership, role=role)
    tasks.import_document(state, meta(), xml(), 'Subject1')
    client = APIClient()
    client.cookies[settings.ACCESS_TOKEN_COOKIE] = str(RefreshToken.for_user(user).access_token)
    response = client.post(
        '/api/graphql/',
        {
            'query': 'query($tenantId: ID!) { invoices(tenantId:$tenantId) { totalCount items { number } } }',
            'variables': {'tenantId': to_global_id('TenantType', str(state.tenant.pk))},
        },
        format='json',
    ).json()
    if allowed:
        assert response['data']['invoices']['totalCount'] == 1, response
    else:
        assert response['errors'][0]['message'] == 'permission_denied', response


def test_ai_context_requires_permission_and_rejects_foreign_ids(state, user_factory, tenant_membership_factory):
    user = user_factory()
    membership = tenant_membership_factory(tenant=state.tenant, user=user, role=TenantUserRole.MEMBER)
    TenantMembershipRole.objects.filter(membership=membership).delete()
    tasks.import_document(state, meta(), xml(), 'Subject1')
    invoice = Invoice.objects.get()
    with pytest.raises(PermissionDenied):
        invoice_context(state.tenant, user, [{'kind': 'INVOICE_DETAILS', 'invoice_ids': [str(invoice.pk)]}])
    role = OrganizationRole.objects.create(tenant=state.tenant, name='AI invoices')
    role.permissions.add(Permission.objects.get(code='invoices.view'))
    TenantMembershipRole.objects.create(membership=membership, role=role)
    invalidate_user_permissions_cache(user.pk, state.tenant.pk)
    with pytest.raises(PermissionDenied):
        invoice_context(state.tenant, user, [{'kind': 'INVOICE_SELECTION', 'invoice_ids': ['foreign-id']}])
    data = invoice_context(state.tenant, user, [{'kind': 'INVOICE_LIST', 'filters': {'direction': 'SALE'}}])
    assert data[0]['total_count'] == 1
    assert data[0]['summary_by_currency'][0]['gross'] == Decimal('123')
    assert 'raw_xml' not in data[0]['invoices'][0]
    assert 'secret' not in str(data)


@patch('apps.invoices.tasks.sync_invoices.apply_async')
def test_backup_restore_and_resync_preserve_category(enqueue, state):
    tasks.import_document(state, meta(), xml(), 'Subject1')
    invoice = Invoice.objects.get()
    category = InvoiceCategory.objects.create(tenant=state.tenant, name='My category')
    invoice.category = category
    invoice.save()
    state.checkpoints = {'Subject1': timezone.now().isoformat()}
    state.save()
    active = InvoiceSyncRun.objects.create(state=state, tenant=state.tenant)
    backup = BackupService(str(state.tenant_id), selected_modules=['invoices']).generate_xml()
    assert 'InvoiceSyncState' not in backup
    assert 'My category' in backup
    Invoice.objects.all().delete()
    category.delete()
    counts = RestoreService(str(state.tenant_id)).restore_from_xml(backup)
    assert counts['Invoice']['created'] == 1, counts
    restored = Invoice.objects.get()
    assert restored.raw_xml == xml()
    assert restored.category.name == 'My category'
    assert restored.lines.count() == 1
    state.refresh_from_db()
    active.refresh_from_db()
    assert state.checkpoints == {}
    assert active.status == 'FAILED'
    tasks.import_document(state, meta(), xml(), 'Subject1')
    assert Invoice.objects.count() == 1
    assert Invoice.objects.get().category.name == 'My category'


def test_encrypted_multipart_package_hashes_and_empty_export(state):
    payload = io.BytesIO()
    metadata = meta()
    with zipfile.ZipFile(payload, 'w', zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr('_metadata.json', json.dumps({'invoices': [metadata]}))
        zipped.writestr(metadata['ksefNumber'] + '.xml', xml(2))
    key, iv = os.urandom(32), os.urandom(16)
    pending = {'secret': crypto.encrypt_token(state.tenant_id, json.dumps({'key': key.hex(), 'iv': iv.hex()})).hex()}
    archive = payload.getvalue()
    contents, parts = {}, []
    for ordinal, plain in enumerate([archive[: len(archive) // 2], archive[len(archive) // 2 :]], 1):
        padder = symmetric_padding.PKCS7(128).padder()
        padded = padder.update(plain) + padder.finalize()
        encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        encrypted = encryptor.update(padded) + encryptor.finalize()
        url = f'https://test.blob.core.windows.net/export/{ordinal}'
        contents[url] = encrypted
        parts.append(
            {
                'url': url,
                'ordinalNumber': ordinal,
                'method': 'GET',
                'encryptedPartSize': len(encrypted),
                'encryptedPartHash': base64.b64encode(hashlib.sha256(encrypted).digest()).decode(),
                'partHash': base64.b64encode(hashlib.sha256(plain).digest()).decode(),
            }
        )

    def handler(request):
        assert 'authorization' not in request.headers
        return httpx.Response(200, content=contents[str(request.url)])

    download = httpx.Client(transport=httpx.MockTransport(handler))
    session = KsefSession(state.context_nip, 'secret', http=download)
    with patch('apps.invoices.ksef.httpx.Client', return_value=download):
        result = session.read_package({'parts': list(reversed(parts)), 'invoiceCount': 1}, pending, state.tenant_id)
    assert result == [(metadata, xml(2))]
    assert session.read_package({'parts': [], 'invoiceCount': 0}, {}, state.tenant_id) == []


@patch('apps.invoices.tasks.sync_invoices.apply_async')
def test_resume_stale_worker_and_avoid_duplicate_active_execution(enqueue, state):
    run = InvoiceSyncRun.objects.create(state=state, tenant=state.tenant, status='RUNNING', heartbeat_at=timezone.now())
    with patch('apps.invoices.tasks.KsefSession') as factory:
        tasks.sync_invoices(run.pk)
        factory.assert_not_called()
        run.heartbeat_at = timezone.now() - timedelta(minutes=31)
        run.save()
        factory.return_value.__enter__.return_value.start_export.return_value = {'reference': 'resumed'}
        tasks.sync_invoices(run.pk)
        factory.assert_called_once()
    run.refresh_from_db()
    assert run.status == 'QUEUED'
    assert run.pending_export['reference'] == 'resumed'


def authenticated_client(user):
    api = APIClient()
    api.cookies[settings.ACCESS_TOKEN_COOKIE] = str(RefreshToken.for_user(user).access_token)
    return api


def test_graphql_csv_all_filtered_rows_and_xml_authorization(state, user_factory, tenant_membership_factory):
    user = user_factory()
    membership = tenant_membership_factory(tenant=state.tenant, user=user, role=TenantUserRole.MEMBER)
    TenantMembershipRole.objects.filter(membership=membership).delete()
    role = OrganizationRole.objects.create(tenant=state.tenant, name='Export invoices')
    role.permissions.add(*Permission.objects.filter(code__in=['invoices.view', 'invoices.export']))
    TenantMembershipRole.objects.create(membership=membership, role=role)
    for i in range(26):
        tasks.import_document(state, meta(str(i)), xml().replace('FV/1', '=unsafe-text'), 'Subject1')
    invoice = Invoice.objects.first()
    query = (
        'query($tenantId:ID!, $id:ID!){ invoiceCsv(tenantId:$tenantId,filters:{direction:"SALE"}) '
        'invoiceXml(tenantId:$tenantId,id:$id) }'
    )
    variables = {'tenantId': to_global_id('TenantType', str(state.tenant.pk)), 'id': str(invoice.pk)}
    response = (
        authenticated_client(user).post('/api/graphql/', {'query': query, 'variables': variables}, format='json').json()
    )
    assert response['data']['invoiceXml'] == invoice.raw_xml, response
    csv_text = response['data']['invoiceCsv']
    assert len(list(csv.reader(io.StringIO(csv_text), delimiter=';'))) == 27
    assert "'=unsafe-text" in csv_text
    role.permissions.remove(Permission.objects.get(code='invoices.export'))
    invalidate_user_permissions_cache(user.pk, state.tenant.pk)
    denied = (
        authenticated_client(user).post('/api/graphql/', {'query': query, 'variables': variables}, format='json').json()
    )
    assert denied['errors'][0]['message'] == 'permission_denied'


def test_ai_response_cites_component_sources_without_write_tools(settings):
    settings.OPENAI_API_KEY = 'test-only'
    events = AsyncMock()
    component_data = [{'invoices': [{'number': 'FV/1', 'id': 'invoice-1'}]}]
    with patch.object(AiChatSubscription, 'broadcast', events), patch(
        'apps.integrations.ai_assistant.subscription.MCPClient'
    ) as mcp, patch('apps.integrations.ai_assistant.subscription.openai.OpenAI') as ai:
        mcp.return_value.list_tools.return_value = []
        ai.return_value.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='FV/1', tool_calls=None))]
        )
        asyncio.run(
            SendAiMessageMutation._process_message(
                1, 'Explain', 'tenant', 'conversation', [], 'fake-jwt', component_data
            )
        )
    text = ''.join(call.kwargs['payload'].get('text', '') for call in events.call_args_list)
    assert text == '[FV/1](invoice:invoice-1)'
    assert events.call_args_list[-1].kwargs['payload']['event_type'] == 'done'
    mcp.return_value.call_tool.assert_not_called()


@patch('apps.invoices.tasks.sync_invoices.apply_async')
def test_cancelled_or_replaced_worker_cannot_publish_checkpoint(enqueue, state):
    run = InvoiceSyncRun.objects.create(state=state, tenant=state.tenant, pending_export={'reference': 'export'})

    def replace_lease(*_):
        InvoiceSyncRun.objects.filter(pk=run.pk).update(execution_token=uuid.uuid4())
        return [(meta(), xml())]

    with patch('apps.invoices.tasks.KsefSession') as factory:
        session = factory.return_value.__enter__.return_value
        session.export_status.return_value = {
            'isTruncated': False,
            'permanentStorageHwmDate': timezone.now().isoformat(),
        }
        session.read_package.side_effect = replace_lease
        tasks.sync_invoices(run.pk)
    state.refresh_from_db()
    assert state.checkpoints == {}
    assert not Invoice.objects.exists()


def test_negative_correction_keeps_amount_signs(state):
    correction = (
        xml(kind='KOR').replace('>100.00<', '>-100.00<').replace('>23.00<', '>-23.00<').replace('>123.00<', '>-123.00<')
    )
    tasks.import_document(state, meta(), correction, 'Subject2')
    invoice = Invoice.objects.get()
    assert invoice.net == Decimal('-100') and invoice.gross == Decimal('-123')
    assert invoice.corrected_ksef_numbers == ['original-not-imported']


@pytest.mark.parametrize(
    'field', ['number', 'counterparty', 'direction', 'issue_date', 'currency', 'net', 'vat', 'gross', 'category__name']
)
def test_table_column_sorting_is_applied_before_pagination(state, field):
    tasks.import_document(state, meta('one'), xml(), 'Subject1')
    tasks.import_document(state, meta('two'), xml(), 'Subject2')
    first, second = list(Invoice.objects.order_by('pk'))
    first.number, second.number = 'A', 'Z'
    first.buyer_name, second.seller_name = 'A buyer', 'Z seller'
    first.issue_date, second.issue_date = date(2026, 1, 1), date(2026, 2, 1)
    first.currency, second.currency = 'EUR', 'PLN'
    first.net, second.net = Decimal('1'), Decimal('2')
    first.vat, second.vat = Decimal('1'), Decimal('2')
    first.gross, second.gross = Decimal('1'), Decimal('2')
    first.category = InvoiceCategory.objects.create(tenant=state.tenant, name='A')
    second.category = InvoiceCategory.objects.create(tenant=state.tenant, name='Z')
    first.save()
    second.save()
    expected = [second.pk, first.pk] if field == 'direction' else [first.pk, second.pk]
    assert list(invoice_queryset(state.tenant, sort=field).values_list('pk', flat=True)) == expected
    assert list(invoice_queryset(state.tenant, sort='-' + field).values_list('pk', flat=True)) == list(
        reversed(expected)
    )
    assert invoice_queryset(state.tenant, sort=field).first().pk == expected[0]
