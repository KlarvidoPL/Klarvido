from django.contrib import admin

from . import models


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


@admin.register(models.TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "role", "user", "invitee_email_address", "tenant", "is_accepted")
