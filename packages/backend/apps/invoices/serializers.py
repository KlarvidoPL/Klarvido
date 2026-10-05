from django.shortcuts import get_object_or_404
from rest_framework import serializers

from apps.multitenancy.constants import ActionType
from common.action_logging.service import log_action
from . import services
from .models import InvoiceCategory
from .query import invoice_queryset


class StartInvoiceSyncSerializer(serializers.Serializer):
    tenant_id = serializers.CharField(write_only=True)
    start_date = serializers.DateField(required=False, write_only=True)
    run_id = serializers.IntegerField(read_only=True)

    def create(self, validated_data):
        request = self.context['request']
        run = services.start_sync(request.tenant, request.user, validated_data.get('start_date'))
        return {'run_id': run.pk}


class SetInvoiceCategorySerializer(serializers.Serializer):
    tenant_id = serializers.CharField(write_only=True)
    invoice_id = serializers.CharField(write_only=True)
    category_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    ok = serializers.BooleanField(read_only=True)

    def create(self, validated_data):
        request = self.context['request']
        invoice = get_object_or_404(invoice_queryset(request.tenant), pk=validated_data['invoice_id'])
        category_id = validated_data.get('category_id')
        category = get_object_or_404(InvoiceCategory, pk=category_id, tenant=request.tenant) if category_id else None
        invoice.category = category
        invoice.save(update_fields=['category', 'updated_at'])
        log_action(
            tenant_id=request.tenant.pk,
            action_type=ActionType.UPDATE,
            entity_type='invoice',
            entity_id=str(invoice.pk),
            entity_name=invoice.number,
            actor_user=request.user,
            metadata={'operation': 'categorize', 'category_id': category_id},
        )
        return {'ok': True}
