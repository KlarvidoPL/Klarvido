"""Filter authentication material before monitoring export."""
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import ignore_logger
from sentry_sdk.scope import add_global_event_processor
from rest_framework_simplejwt.exceptions import InvalidToken

from .redaction import _redact, CredentialSafeFormatter

__all__ = ['processor', 'init', 'CredentialSafeFormatter']

ignore_logger('graphql.execution.utils')


def processor(event, hint):
    if event.get('type') == 'transaction' and event.get('transaction') == '/lbcheck':
        return None
    return _redact(event)


# Registration returns None; keep the function callable for the export callbacks.
add_global_event_processor(processor)


def init(dsn, environment_name, traces_sample_rate):
    sentry_sdk.init(
        dsn=dsn,
        integrations=[DjangoIntegration()],
        traces_sample_rate=traces_sample_rate,
        send_default_pii=False,
        include_local_variables=False,
        environment=environment_name,
        before_send=processor,
        before_send_transaction=processor,
        before_breadcrumb=lambda crumb, hint: _redact(crumb),
        ignore_errors=[InvalidToken],
    )
