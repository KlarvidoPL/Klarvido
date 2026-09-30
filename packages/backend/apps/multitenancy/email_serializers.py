from rest_framework import serializers


class TenantInvitationEmailSerializer(serializers.Serializer):
    token = serializers.CharField()
    tenant_membership_id = serializers.CharField()


class TenantDeletedEmailSerializer(serializers.Serializer):
    tenant_name = serializers.CharField()
    deleted_by = serializers.CharField()
    # The member who deleted it gets a confirmation ("You deleted..."), everyone else a heads-up
    is_deleter = serializers.BooleanField()
