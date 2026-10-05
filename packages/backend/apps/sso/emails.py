from apps.users.notifications import UserEmail
from . import email_serializers


class SSODomainRecordMissingEmail(UserEmail):
    name = "SSO_DOMAIN_RECORD_MISSING"
    serializer_class = email_serializers.SSODomainRecordMissingEmailSerializer


class SSODomainLapsedEmail(UserEmail):
    name = "SSO_DOMAIN_LAPSED"
    serializer_class = email_serializers.SSODomainLapsedEmailSerializer
