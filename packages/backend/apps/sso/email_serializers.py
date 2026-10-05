from rest_framework import serializers


class SSODomainRecordMissingEmailSerializer(serializers.Serializer):
    domain = serializers.CharField()
    tenant_name = serializers.CharField()
    grace_days = serializers.IntegerField()


class SSODomainLapsedEmailSerializer(serializers.Serializer):
    domain = serializers.CharField()
    tenant_name = serializers.CharField()
    grace_days = serializers.IntegerField()
