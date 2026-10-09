from django.contrib import admin
from django.db import transaction

from . import models
from .constants import TenantType
from .services.deletion import delete_organization


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
        delete_organization(obj.pk, request, via_admin=True)

    def delete_queryset(self, request, queryset):
        # Stable lock ordering prevents bulk deletions deadlocking each other.
        # An error must roll back the entire selection, including cleanup jobs.
        with transaction.atomic():
            tenants = list(queryset.select_for_update().order_by('pk'))
            for tenant in tenants:
                delete_organization(tenant.pk, request, via_admin=True)


@admin.register(models.TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "role", "user", "invitee_email_address", "tenant", "is_accepted")
