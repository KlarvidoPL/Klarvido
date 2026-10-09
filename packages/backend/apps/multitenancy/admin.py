from django.contrib import admin
from django.contrib.admin.actions import delete_selected as django_delete_selected
from django.core.exceptions import PermissionDenied
from common.graphql.exceptions import GraphQlValidationError
from django.db import transaction

from . import models
from .constants import TenantType
from .services.deletion import delete_organization, require_deletion_otp


@admin.register(models.OrganizationDeletionDelivery)
class OrganizationDeletionDeliveryAdmin(admin.ModelAdmin):
    list_display = ('id', 'organization_id', 'channel', 'attempts', 'next_attempt_at', 'completed_at', 'last_error')
    list_filter = ('channel', 'completed_at')
    search_fields = ('organization_id', 'recipient_email')
    readonly_fields = [field.name for field in models.OrganizationDeletionDelivery._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.ResourceCleanup)
class ResourceCleanupAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'organization_id',
        'resource_type',
        'attempts',
        'next_attempt_at',
        'completed_at',
        'last_error',
    )
    list_filter = ('resource_type', 'completed_at')
    search_fields = ('organization_id', 'resource_path')
    readonly_fields = [field.name for field in models.ResourceCleanup._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "type")
    actions = ['delete_selected']
    delete_confirmation_template = 'admin/multitenancy/tenant/delete_confirmation.html'
    delete_selected_confirmation_template = 'admin/multitenancy/tenant/delete_selected_confirmation.html'

    def delete_view(self, request, object_id, extra_context=None):
        context = dict(extra_context or {})
        if request.method == 'POST':
            obj = self.get_object(request, object_id)
            if obj is not None and not self.has_delete_permission(request, obj):
                raise PermissionDenied
            try:
                # Django wraps delete_view in atomic(). Validate first so failed
                # OTP attempt counters survive returning the confirmation page.
                require_deletion_otp(request, getattr(request, 'POST', {}).get('otp_token'))
            except GraphQlValidationError as exc:
                context['otp_error'] = str(exc.detail['otp_token'][0])
                original_method = request.method
                request.method = 'GET'
                try:
                    return super().delete_view(request, object_id, extra_context=context)
                finally:
                    request.method = original_method
        return super().delete_view(request, object_id, extra_context=context)

    @admin.action(description=django_delete_selected.short_description, permissions=['delete'])
    def delete_selected(self, request, queryset):
        error = None
        if request.POST.get('post'):
            if not self.has_delete_permission(request):
                raise PermissionDenied
            try:
                require_deletion_otp(request, getattr(request, 'POST', {}).get('otp_token'))
            except GraphQlValidationError as exc:
                error = str(exc.detail['otp_token'][0])
        original_post = request.POST
        if error:
            request.POST = request.POST.copy()
            request.POST.pop('post', None)
        try:
            response = django_delete_selected(self, request, queryset)
            if error and response is not None:
                response.context_data['otp_error'] = error
            return response
        finally:
            request.POST = original_post

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.type == TenantType.DEFAULT:
            return False
        return super().has_delete_permission(request, obj)

    def get_deleted_objects(self, objs, request):
        deleted_objects, model_count, perms_needed, protected = super().get_deleted_objects(objs, request)
        # Also block mixed bulk selections before Django renders its confirmation.
        if any(obj.type == TenantType.DEFAULT for obj in objs):
            protected.append('Cannot delete default type tenant.')
        return deleted_objects, model_count, perms_needed, protected

    def log_deletions(self, request, queryset):
        # The shared service writes the detailed durable audit record atomically
        # with deletion. Avoid Django's earlier, duplicate generic audit entries.
        return []

    def delete_model(self, request, obj):
        delete_organization(obj.pk, request, via_admin=True, otp_token=getattr(request, 'POST', {}).get('otp_token'))

    def delete_queryset(self, request, queryset):
        if not self.has_delete_permission(request):
            raise PermissionDenied
        require_deletion_otp(request, getattr(request, 'POST', {}).get('otp_token'))
        # Stable lock ordering prevents bulk deletions deadlocking each other.
        # An error must roll back the entire selection, including cleanup jobs.
        with transaction.atomic():
            tenants = list(queryset.select_for_update().order_by('pk'))
            for tenant in tenants:
                delete_organization(tenant.pk, request, via_admin=True)


@admin.register(models.TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "role", "user", "invitee_email_address", "tenant", "is_accepted")
