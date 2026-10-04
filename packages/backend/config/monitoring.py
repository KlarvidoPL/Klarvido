import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import ignore_logger
from sentry_sdk.scope import add_global_event_processor
from rest_framework_simplejwt.exceptions import InvalidToken

ignore_logger("graphql.execution.utils")


SENSITIVE_KEY_FRAGMENTS = ("token", "password", "secret")


def _is_sensitive(key) -> bool:
    return any(fragment in str(key).lower() for fragment in SENSITIVE_KEY_FRAGMENTS)


def _redact(value):
    """Recursively replace values of sensitive-looking keys, so credentials in request bodies never reach Sentry."""
    if isinstance(value, dict):
        return {key: "[Filtered]" if _is_sensitive(key) else _redact(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


@add_global_event_processor
def processor(event, hint):
    if event.get("type") == "transaction" and event.get("transaction") == "/lbcheck":
        return None
    request = event.get("request")
    if isinstance(request, dict) and request.get("data") is not None:
        request["data"] = _redact(request["data"])
    return event


def init(dsn, environment_name, traces_sample_rate):
    sentry_sdk.init(
        dsn=dsn,
        integrations=[DjangoIntegration()],
        traces_sample_rate=traces_sample_rate,
        send_default_pii=True,
        # Local variables of every stack frame would otherwise be sent, including plaintext KSeF tokens
        include_local_variables=False,
        environment=environment_name,
        ignore_errors=[InvalidToken],
    )
